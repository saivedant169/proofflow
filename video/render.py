"""Render an explicitly edited walkthrough from approved, actual app captures.

No browser automation or model calls occur here. Text overlays are editorial
captions; the underlying app captures are never retouched. Requires macOS say,
ffmpeg/ffprobe, and Pillow. Use --audio-only while awaiting final screenshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
ROOT = (HERE / json.loads((HERE / "manifest.json").read_text())["source_root"]).resolve()
WORK = HERE / ".work"
INK = "#101318"
MUTED = "#59616e"
BLUE = "#2450e6"
FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")


def run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True)


def duration(path: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "json", str(path)], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def resolve_image(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Screenshot must be inside the ProofFlow project")
    if not path.is_file():
        raise ValueError(f"Missing approved screenshot: {path}")
    return path


def wrap_pixels(draw: ImageDraw.ImageDraw, value: str, face, max_width: int) -> list[str]:
    lines, current = [], ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=face) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def csv_panel(width: int, height: int) -> Image.Image:
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((96, 70), "Bring the same runtime to your data.", font=font(48, True), fill=INK)
    draw.text((96, 145), "Bounded CSV import · Explicit exchange rates · Versioned refresh", font=font(27), fill=MUTED)
    draw.rounded_rectangle((96, 235, width - 96, 440), radius=12, fill="#f2f5f9", outline="#d9dfe8")
    lines = ["python scripts/import_csv.py my-orders.csv \\", "    --workspace my-orders --region EMEA --fx EUR=1.10"]
    for index, line in enumerate(lines):
        draw.text((126, 280 + index * 62), line, font=font(30), fill=INK)
    draw.text((96, 500), "Required columns", font=font(29, True), fill=INK)
    draw.text((96, 551), "order_id, region, currency, gross_cents", font=font(28), fill=MUTED)
    draw.text((96, 618), "Up to 1 MiB / 1,000 rows. Optional refunds and ticket counts.", font=font(25), fill=MUTED)
    draw.text((96, 674), "CSV import command example", font=font(23), fill=MUTED)
    return canvas


def evidence_card(kind: str, width: int, height: int) -> Image.Image:
    data = json.loads((HERE / "evidence_extract.json").read_text())
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((75, 25), "SAVED EXECUTION EVIDENCE", font=font(20, True), fill=BLUE)
    def line(text, y, size=28, color=MUTED, bold=False):
        draw.text((75, y), text, font=font(size, bold), fill=color)
    def metric(x, y, value, label, color=BLUE):
        draw.text((x, y), value, font=font(64, True), fill=color)
        draw.text((x, y+83), label, font=font(25), fill=MUTED)
    def band(y, text, fill="#f2f5f9", color=MUTED, size=24):
        draw.rounded_rectangle((60, y, width-60, y+75), radius=10, fill=fill)
        draw.text((82,y+23),text,font=font(size),fill=color)
    if kind == "matched":
        line("Complete dependencies versus retrieval", 75, 43, INK, True)
        line("Recoverable affected reports refreshed · 10 held-out retail cases", 135, 26)
        rows = data["matched"]
        names = {"graph":"ProofFlow / HydraDB", "exact_flat":"Exact dependency traversal", "bm25":"BM25", "dense":"Dense BGE", "iterative_hybrid":"Iterative hybrid"}
        ordered=[next(a for a in rows if a["arm"]==name) for name in names]
        for i,row in enumerate(ordered):
            y=203+i*73
            c=BLUE if row["arm"]=="graph" else "#8693b6" if row["arm"]=="exact_flat" else "#adb4c2"
            if i==0: draw.rounded_rectangle((60,y-7,width-60,y+61),radius=8,fill="#f2f4fc")
            draw.text((80,y+9),names[row["arm"]],font=font(28,i==0),fill=INK)
            draw.rounded_rectangle((680,y+12,1380,y+43),radius=5,fill="#eceff4")
            draw.rounded_rectangle((680,y+12,680+round(700*row["fresh_affected_reports"]/38),y+43),radius=5,fill=c)
            draw.text((1450,y),f'{row["fresh_affected_reports"]} / 38',font=font(35,True),fill=c if i<2 else INK)
        line("Same records · Shared Hydra-assisted currentness and refresh executor", 595, 26)
        line("Allowance set by complete graph closure before comparator runs: 0–9,611 tokens", 646, 25)
        band(700,"Exact dependency traversal ties ProofFlow. Both use explicit dependencies.",size=25)
    elif kind == "tokens":
        p=data["primary"]
        line("Less evidence, complete refresh",75,45,INK,True)
        metric(75,170,f'{100*p["token_savings_fraction"]:.2f}%',"fewer evidence tokens than full context")
        metric(1000,170,f'{p["graph_tokens"]:,}',"graph evidence tokens")
        metric(1000,365,f'{p["full_context_tokens"]:,}',"full-context evidence tokens")
        line("All 38 recoverable affected reports refreshed", 390, 32, INK, True)
        line("4 unavailable reports correctly blocked", 442, 28)
        band(535,"Complete graph, exact traversal and full context each execute 101 tools.",size=25)
        line("Aggregate includes a no-op. Excluding it: 33.99% of full-context evidence.",645,25)
        line("Evidence-token reduction; not model-cost savings. No model runs in this benchmark.",700,25)
    elif kind == "limits":
        line("Two limits, retained in the results",75,45,INK,True)
        draw.rounded_rectangle((60,160,850,530),radius=12,fill="#f4f5f8")
        draw.rounded_rectangle((895,160,width-60,530),radius=12,fill="#fbf6e9")
        draw.text((85,185),"Fixed 2,048-token condition",font=font(31,True),fill=INK)
        draw.text((85,245),"8 / 38",font=font(70,True),fill=BLUE)
        draw.text((85,335),"ProofFlow affected reports refreshed",font=font(25),fill=MUTED)
        draw.text((85,400),"BM25 1 · Dense 0 · Iterative 4",font=font(25),fill=INK)
        draw.text((85,456),"Exact dependency traversal also 8/38",font=font(23),fill=MUTED)
        draw.text((920,185),"Development efficiency gate",font=font(31,True),fill=INK)
        draw.text((920,245),"FAILED",font=font(61,True),fill="#806517")
        draw.text((920,335),"60.79% of full-context evidence",font=font(27),fill=INK)
        draw.text((920,400),"Unchanged target: ≤40%",font=font(27),fill=MUTED)
        draw.text((920,456),"Correctness passed on 4 development cases",font=font(23),fill=MUTED)
        line("At the fixed cap, every arm's 2/10 correct endstates are refusal + no-op.",590,26)
        line("Development is separate from held-out test. Its no-op-excluded ratio is 81.07%.",645,25)
        line("Full per-case results and limitations remain in the accompanying report.",700,25)
    elif kind == "mcp":
        m=data["mcp"]
        line("A Claude client chose and executed both plans",75,43,INK,True)
        line("Fable 5.2/high · One local run after configuration fix · Authored two-row CSV",140,27)
        metric(75,215,f'{m["passed_checks"]} / {m["total_checks"]}',"recorded checks passed")
        metric(660,215,str(m["requests"]),"MCP requests")
        metric(1200,215,str(m["runtime_calls"]),"recorded runtime calls")
        line("Five tools: load_csv · prepare · execute_plan · inspect · refresh",390,31,INK,True)
        line("7 initial calculations + 1 reused composition + 4 affected refresh calls",450,27)
        line("Two CSV loads also perform 16 arithmetic preflight calculations.",506,26)
        band(570,"First launch failed before tool discovery. That configuration failure is retained.",fill="#fbf6e9",size=25)
        line("Server makes no model calls; the external Claude client does. Separate from retail.",680,25)
        line("One local integration demonstration; not a general agent-reliability result.",730,24)
    else:
        raise ValueError(f"Unknown evidence card: {kind}")
    return canvas


def make_base(scene: dict, index: int, total: int, width: int, height: int) -> Image.Image:
    frame = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(frame)
    draw.text((40, 24), "ProofFlow", font=font(28, True), fill=INK)
    title = scene["title"]
    draw.text((220, 28), title, font=font(24), fill=MUTED)
    draw.text((width - 100, 28), f"{index + 1:02}/{total:02}", font=font(22), fill=MUTED)
    draw.line((40, 72, width - 40, 72), fill="#d9dfe8", width=1)

    if scene.get("image"):
        capture = Image.open(resolve_image(scene["image"])).convert("RGB")
        if "crop_box" in scene:
            box = scene["crop_box"]
            if len(box) != 4 or not (0 <= box[0] < box[2] <= capture.width and 0 <= box[1] < box[3] <= capture.height):
                raise ValueError(f"Invalid crop bounds for {scene['id']}")
            capture = capture.crop(box)
    elif scene.get("card"):
        capture = evidence_card(scene["card"], 1760, 790)
    elif scene["id"] == "csv":
        capture = csv_panel(1760, 790)
    else:
        raise ValueError("Every app scene needs a real approved capture")

    available = (width - 80, height - 246)
    ratio = min(available[0] / capture.width, available[1] / capture.height)
    size = (round(capture.width * ratio), round(capture.height * ratio))
    capture = capture.resize(size, Image.Resampling.LANCZOS)
    frame.paste(capture, ((width - size[0]) // 2, 87 + (available[1] - size[1]) // 2))
    draw.text((40, height - 28), scene.get("footer", "Edited app captures · Saved evidence"), font=font(16), fill=MUTED)
    return frame


def chunks(text: str, max_words: int = 14) -> list[str]:
    for phrase in ("B M twenty-five", "Hydra D B", "E U", "C S V", "M C P"):
        text = text.replace(phrase, phrase.replace(" ", "~"))
    pieces = []
    for sentence in re.split(r"(?<=[.!?;])\s+", text):
        words = sentence.split()
        remaining_chunks = math.ceil(len(words) / max_words)
        while words:
            take = math.ceil(len(words) / remaining_chunks)
            pieces.append(" ".join(words[:take]).replace("~", " "))
            words = words[take:]
            remaining_chunks -= 1
    return pieces


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remaining = divmod(milliseconds, 3_600_000)
    minutes, remaining = divmod(remaining, 60_000)
    secs, ms = divmod(remaining, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def display_caption(text: str) -> str:
    replacements = {
        "Hydra D B": "HydraDB", "E U": "EU", "C S V": "CSV",
        "B M twenty-five": "BM25", "Fable five point two": "Fable 5.2", "M C P": "MCP",
        "one point one zero": "1.10", "one point two zero": "1.20",
        "two-thousand-forty-eight-token": "2,048-token",
        "sixteen of twenty-nine": "16 of 29", "all twenty-nine": "all 29",
        "thirty-eight": "38", "thirty-two": "32", "two-thousand-forty-eight-token": "2,048-token",
        "sixty-nine point four one percent": "69.41%",
    }
    for spoken, written in replacements.items():
        text = text.replace(spoken, written)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=HERE / "manifest.json")
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    scenes = manifest["scenes"]
    if not args.audio_only and manifest.get("screens_approved") is not True:
        raise ValueError("Source screenshots must be marked as reviewed before rendering")
    if not args.audio_only:
        for scene in scenes:
            if scene.get("image"):
                resolve_image(scene["image"])
            if scene.get("lead_image"):
                resolve_image(scene["lead_image"])
    WORK.mkdir(parents=True, exist_ok=True)
    narration = []
    for scene in scenes:
        text_path = WORK / f"{scene['id']}.txt"
        aiff = WORK / f"{scene['id']}.aiff"
        text_path.write_text(scene["narration"])
        run("say", "-v", manifest["voice"], "-r", str(manifest["rate"]), "-f", str(text_path), "-o", str(aiff))
        narration.append({"scene": scene["id"], "path": aiff, "raw_seconds": duration(aiff)})
    raw_total = sum(item["raw_seconds"] for item in narration)
    padding = 0.65
    target = float(manifest["target_duration_seconds"])
    speed = raw_total / (target - padding * len(scenes))
    if not 0.8 <= speed <= 1.25:
        raise ValueError(f"Narration would need unnatural pacing ({speed:.3f}); revise speech rate")
    audio_data = {"voice": manifest["voice"], "rate": manifest["rate"], "raw_seconds": raw_total,
                  "speed_adjustment": speed, "target_seconds": target,
                  "scenes": [{k: str(v) if isinstance(v, Path) else v for k, v in item.items()} for item in narration]}
    (WORK / "audio-preview.json").write_text(json.dumps(audio_data, indent=2) + "\n")
    print(json.dumps(audio_data, indent=2), flush=True)
    if args.audio_only:
        return

    width, height = int(manifest["width"]), int(manifest["height"])
    for old_frame in WORK.glob("frame-*.png"):
        old_frame.unlink()
    frame_entries, subtitle_entries, sound_entries, source_hashes, timing = [], [], [], {}, []
    cursor = 0.0
    for index, (scene, recorded) in enumerate(zip(scenes, narration)):
        speech_seconds = recorded["raw_seconds"] / speed
        scene_seconds = speech_seconds + padding
        sound = WORK / f"{scene['id']}.wav"
        run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(recorded["path"]),
            "-af", f"atempo={speed:.8f},apad=pad_dur={padding},loudnorm=I=-16:TP=-1.5:LRA=11",
            "-t", f"{scene_seconds:.8f}", "-ar", "48000", "-ac", "1", str(sound))
        sound_entries.append(f"file '{sound.as_posix()}'")
        base = make_base(scene, index, len(scenes), width, height)
        lead_base = None
        if scene.get("lead_image"):
            lead_scene = {**scene, "image": scene["lead_image"], "crop_box": scene["lead_crop_box"]}
            lead_base = make_base(lead_scene, index, len(scenes), width, height)
        captions = chunks(scene["narration"])
        word_total = sum(len(piece.split()) for piece in captions)
        scene_start = cursor
        for piece_index, piece in enumerate(captions):
            duration_seconds = speech_seconds * len(piece.split()) / word_total
            if piece_index == len(captions) - 1:
                duration_seconds += padding
            frame = (lead_base if lead_base is not None and piece_index < scene["lead_caption_count"] else base).copy()
            draw = ImageDraw.Draw(frame)
            draw.rounded_rectangle((40, height - 145, width - 40, height - 47), radius=10, fill=INK)
            caption = display_caption(piece)
            lines = wrap_pixels(draw, caption, font(32), width - 160)
            if len(lines) > 2:
                raise ValueError("Caption exceeds two readable lines")
            y = height - 123 if len(lines) == 1 else height - 137
            for line in lines:
                length = draw.textlength(line, font=font(32))
                draw.text(((width - length) / 2, y), line, font=font(32), fill="white")
                y += 39
            frame_path = WORK / f"frame-{index:02}-{piece_index:02}.png"
            frame.save(frame_path)
            frame_entries.extend([f"file '{frame_path.as_posix()}'", f"duration {duration_seconds:.8f}"])
            subtitle_entries.append(f"{len(subtitle_entries)+1}\n{timestamp(cursor)} --> {timestamp(cursor+duration_seconds)}\n{caption}\n")
            cursor += duration_seconds
        timing.append({"scene": scene["id"], "start": scene_start, "end": cursor,
                       "image": scene.get("image"), "crop_box": scene.get("crop_box")})
        if scene.get("image"):
            source_hashes[scene["image"]] = digest(resolve_image(scene["image"]))
        if scene.get("lead_image"):
            source_hashes[scene["lead_image"]] = digest(resolve_image(scene["lead_image"]))
    frame_entries.append(frame_entries[-2])  # Last still must have a terminal frame.
    frames_file = WORK / "frames.ffconcat"
    frames_file.write_text("ffconcat version 1.0\n" + "\n".join(frame_entries) + "\n")
    sounds_file = WORK / "sound.ffconcat"
    sounds_file.write_text("ffconcat version 1.0\n" + "\n".join(sound_entries) + "\n")
    subtitles = HERE / "captions.srt"
    subtitles.write_text("\n".join(subtitle_entries))
    audio = WORK / "narration.wav"
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(sounds_file), "-c:a", "pcm_s16le", str(audio))
    destination = HERE / "proofflow-walkthrough.mp4"
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(frames_file), "-i", str(audio), "-i", str(subtitles), "-map", "0:v:0", "-map", "1:a:0",
        "-map", "2:s:0", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-r", str(manifest["fps"]), "-vf", f"fps={manifest['fps']},tpad=stop_mode=clone:stop_duration=1",
        "-af", f"apad=whole_dur={target}", "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text",
        "-disposition:s:0", "0", "-t", str(target), "-movflags", "+faststart", str(destination))
    metadata = {"format": manifest["format"], "duration_seconds": duration(destination),
                "bytes": destination.stat().st_size, "sha256": digest(destination),
                "source_image_sha256": source_hashes, "narration": audio_data, "scenes": timing,
                "captions": "Burned editorial captions plus an optional embedded text track.",
                "hosting_url": manifest.get("hosting_url"), "screens_approved": True,
                "release_approved": manifest.get("release_approved", False), "predecessor_video_sha256": manifest.get("original_video_sha256"),
                "source_evidence_sha256": {name: digest(ROOT / name) for name in manifest["source_evidence"]},
                "evidence_extract_sha256": digest(HERE / "evidence_extract.json")}
    (HERE / "render_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"video": str(destination), "duration_seconds": metadata["duration_seconds"],
                      "megabytes": metadata["bytes"] / 1_000_000}), flush=True)


if __name__ == "__main__":
    main()
