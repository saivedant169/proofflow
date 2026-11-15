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
ROOT = HERE.parent
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
    path = (HERE / value).resolve()
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
    elif scene["id"] == "csv":
        capture = csv_panel(1760, 790)
    else:
        raise ValueError("Every app scene needs a real approved capture")

    available = (width - 80, height - 246)
    ratio = min(available[0] / capture.width, available[1] / capture.height)
    size = (round(capture.width * ratio), round(capture.height * ratio))
    capture = capture.resize(size, Image.Resampling.LANCZOS)
    frame.paste(capture, ((width - size[0]) // 2, 87 + (available[1] - size[1]) // 2))
    draw.text((40, height - 28), "Edited app captures · Authored demo data · Real execution evidence", font=font(16), fill=MUTED)
    return frame


def chunks(text: str, max_words: int = 14) -> list[str]:
    pieces = []
    for sentence in re.split(r"(?<=[.!?;])\s+", text):
        words = sentence.split()
        remaining_chunks = math.ceil(len(words) / max_words)
        while words:
            take = math.ceil(len(words) / remaining_chunks)
            pieces.append(" ".join(words[:take]))
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
        "B M twenty-five": "BM25", "Fable five point two": "Fable 5.2",
        "one point one zero": "1.10", "one point two zero": "1.20",
        "two-thousand-forty-eight-token": "2,048-token",
        "sixteen of twenty-nine": "16 of 29", "all twenty-nine": "all 29",
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
        raise ValueError("Final render waits for parent approval of the exact screen captures")
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
                "hosting_url": manifest.get("hosting_url"), "screens_approved": True}
    (HERE / "render_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"video": str(destination), "duration_seconds": metadata["duration_seconds"],
                      "megabytes": metadata["bytes"] / 1_000_000}), flush=True)


if __name__ == "__main__":
    main()
