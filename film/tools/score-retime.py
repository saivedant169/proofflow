"""Re-time a Lyria RealTime take to new film windows by musical edits only (no time-stretch, no re-pitch).

    python tools/score-retime.py --take audio/music/take3-raw.wav --map audio/music/retime-map.json \
        --out <retimed.wav> --report audio/music/retime.json

The take was steered live along an older timeline, so its arc changes at known source times (the map's `src`
anchors). Each stretch between two anchors is played in order, lengthened or shortened by one jump (two, one per half, for long stretches) inside its
steady middle: a repeat (jump back) or a skip (jump forward) between two moments that sound alike (chroma, timbre,
onset pattern over a +-2.4 s context; the take is ~100 BPM, so good jumps fall on whole beats or bars). The cut is
refined by waveform cross-correlation (+-30 ms) and crossfaded equal-power over 80 ms. A jump never lands within
4 s after an anchor (the prompt crossfade) or 1.5 s before the next one. Whatever a jump cannot absorb (it moves in
whole beats) carries into the next stretch; anchors listed as tight (s3, the s6 lift, s7, s8, the end) weigh that error more.

map: {"anchors": [{"label": "s3", "src": 40.3, "dst": 41.3}, ...], "end": {"src": 224, "dst": 245.8}, "tight": [labels]}
"""
import argparse
import json

import librosa
import numpy as np
import soundfile as sf

ap = argparse.ArgumentParser()
ap.add_argument("--take", required=True)
ap.add_argument("--map", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--report", required=True)
a = ap.parse_args()

y, sr = sf.read(a.take, dtype="float32", always_2d=True)  # (n, 2) at 48 kHz
mono = librosa.resample(y.mean(axis=1), orig_sr=sr, target_sr=22050)
FS, HOP = 22050, 1024
dt = HOP / FS  # ~46 ms feature frames; the cut itself is refined on the waveform
chroma = librosa.feature.chroma_cqt(y=mono, sr=FS, hop_length=HOP)
mfcc = librosa.feature.mfcc(y=mono, sr=FS, hop_length=HOP, n_mfcc=20)[1:]
onset = librosa.onset.onset_strength(y=mono, sr=FS, hop_length=HOP)[None, :]
n = min(chroma.shape[1], mfcc.shape[1], onset.shape[1])


def z(m):
    m = m[:, :n]
    return (m - m.mean(axis=1, keepdims=True)) / (m.std(axis=1, keepdims=True) + 1e-6)


F = np.vstack([z(chroma) * 1.0, z(mfcc) * 0.7, z(onset) * 1.5])
C = int(round(2.4 / dt))  # +-2.4 s context
LMAX = int(round(20 / dt))
LMIN = int(round(0.55 / dt))
NRM = np.einsum("ij,ij->j", F, F)
csum = lambda v: np.concatenate([[0.0], np.cumsum(v)])
cN = csum(NRM)


def win(c, t):  # windowed sum of a per-frame series around each frame index t (clipped)
    lo = np.clip(t - C, 0, len(c) - 1)
    hi = np.clip(t + C + 1, 0, len(c) - 1)
    return c[hi] - c[lo]


# D[L][x]: 1 - cosine between the +-2.4 s context at frame x and at frame x+L (all lags, vectorised)
lags = [L for L in range(-LMAX, LMAX + 1) if abs(L) >= LMIN]
D = {}
xs_all = np.arange(n)
for L in lags:
    P = np.zeros(n)
    if L > 0:
        P[: n - L] = np.einsum("ij,ij->j", F[:, : n - L], F[:, L:])
    else:
        P[-L:] = np.einsum("ij,ij->j", F[:, -L:], F[:, : n + L])
    num = win(csum(P), xs_all)
    yy = np.clip(xs_all + L, 0, n - 1)
    den = np.sqrt(win(cN, xs_all) * win(cN, yy)) + 1e-9
    D[L] = 1 - num / den

spec = json.load(open(a.map, encoding="utf-8"))
anchors = spec["anchors"]
end = spec["end"]
pts = anchors + [{"label": "end", "src": end["src"], "dst": end["dst"]}]
TIGHT = set(spec.get("tight", ["s3", "lift", "s7", "s8", "end"]))  # anchors that must land within a beat


def best_jump(L, x_lo, x_hi, y_lo, y_hi):
    """lowest-dissimilarity jump of lag L with x in [x_lo, x_hi] and x+L in [y_lo, y_hi] (seconds)"""
    a0 = max(int(np.ceil(x_lo / dt)), int(np.ceil(y_lo / dt)) - L)
    a1 = min(int(np.floor(x_hi / dt)), int(np.floor(y_hi / dt)) - L)
    if a1 < a0:
        return None
    seg = D[L][a0: a1 + 1]
    i = int(np.argmin(seg))
    return float(seg[i]), (a0 + i) * dt, (a0 + i + L) * dt


segments = []  # (src_from, src_to) pieces played in order
edits = []
carry = 0.0  # output time minus target at the current anchor
for k in range(len(pts) - 1):
    p, q = pts[k], pts[k + 1]
    s0, s1 = p["src"], q["src"]
    want = (q["dst"] - p["dst"]) - carry  # output length this stretch should have so q lands on time
    have = s1 - s0
    delta = want - have  # >0: lengthen (repeat = negative lag), <0: shorten (skip = positive lag)
    w = 0.6 if q["label"] in TIGHT else 0.25
    lo, hi = s0 + 4.0, s1 - 1.5  # jump points: clear of the prompt crossfade after an anchor and of the next anchor
    ylo, yhi = s0 + 2.0, s1 - 0.5
    choice = None  # (cost, [(d, x, y), ...])
    if abs(delta) >= 0.3 and hi - lo > 1.0:
        sgn = 1 if delta < 0 else -1
        cand = [L for L in lags if np.sign(L) == sgn and abs(L) * dt <= abs(delta) + 3.0]
        for L in cand:  # one jump
            b = best_jump(L, lo, hi, ylo, yhi)
            if b:
                cost = b[0] + w * abs(delta + L * dt)
                if choice is None or cost < choice[0]:
                    choice = (cost, [b])
        if abs(delta) > 3.0:  # two jumps, one in each half of the stretch
            mid = (lo + hi) / 2
            h1 = {L: best_jump(L, lo, mid - 0.5, ylo, mid - 0.2) for L in cand}
            h2 = {L: best_jump(L, mid + 0.5, hi, mid + 0.2, yhi) for L in cand}
            h1 = {L: b for L, b in h1.items() if b}
            h2 = {L: b for L, b in h2.items() if b}
            for L1, b1 in h1.items():
                for L2, b2 in h2.items():
                    cost = max(b1[0], b2[0]) + 0.03 + w * abs(delta + (L1 + L2) * dt)
                    if choice is None or cost < choice[0]:
                        choice = (cost, [b1, b2])
    cur = s0
    out_len = have
    for d, x, y2 in (choice[1] if choice else []):
        segments.append([cur, x])
        cur = y2
        out_len += x - y2
        edits.append({"stretch": f"{p['label']} -> {q['label']}", "kind": "repeat" if y2 < x else "skip",
                      "at_src": round(x, 3), "to_src": round(y2, 3), "jump_s": round(y2 - x, 3), "dissimilarity": round(d, 3)})
    segments.append([cur, s1])
    carry = carry + out_len - (q["dst"] - p["dst"])
    q["landed"] = round(q["dst"] + carry, 3)
    q["error_s"] = round(carry, 3)

# merge contiguous pieces, then render with refined, crossfaded joins
pieces = []
for s in segments:
    if pieces and abs(pieces[-1][1] - s[0]) < 1e-6:
        pieces[-1][1] = s[1]
    else:
        pieces.append(list(s))
XF = int(0.08 * sr)
out = []
for i, (f0, f1) in enumerate(pieces):
    i0, i1 = int(round(f0 * sr)), int(round(f1 * sr))
    if i > 0:
        # refine the entry point of this piece: best waveform match to the tail of what is already written
        prev = np.concatenate(out[-3:])[-XF:].mean(axis=1) if out else None
        best_l, best_c = 0, -1
        for lag in range(-int(0.030 * sr), int(0.030 * sr) + 1, 8):
            seg = y[i0 + lag - XF: i0 + lag, :].mean(axis=1)
            if len(seg) != XF:
                continue
            c = float(np.dot(seg, prev) / (np.linalg.norm(seg) * np.linalg.norm(prev) + 1e-9))
            if c > best_c:
                best_l, best_c = lag, c
        i0 += best_l
        i1 = max(i1, i0 + XF)
        # equal-power crossfade: tail of output (already contains the XF after the previous cut) with this piece's
        # XF samples before its entry
        tail = out[-1][-XF:].copy()
        head = y[i0 - XF: i0, :]
        tt = np.linspace(0, 1, XF)[:, None]
        out[-1] = out[-1][:-XF]
        out.append(tail * np.cos(tt * np.pi / 2) + head * np.sin(tt * np.pi / 2))
        pieces[i].append(round(best_c, 3))
    out.append(y[i0:i1, :])
res = np.concatenate(out)
sf.write(a.out, res, sr, subtype="PCM_24")
report = {"take": a.take, "pieces_src": [[round(p[0], 3), round(p[1], 3)] for p in pieces],
          "join_xcorr": [p[2] for p in pieces[1:]], "edits": edits,
          "anchors": [{k: v for k, v in p.items()} for p in pts], "out_seconds": round(len(res) / sr, 3)}
json.dump(report, open(a.report, "w", encoding="utf-8"), indent=1)
print(json.dumps(report, indent=1))
