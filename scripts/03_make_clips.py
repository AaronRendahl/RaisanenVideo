#!/usr/bin/env python3
"""
03_make_clips.py

CLI entrypoint to generate derivative MP4 clips (1 file per top-level Clip)
with embedded MP4 chapter markers for subchapters, plus diagnostic frame snapshots.
"""

import sys
import tempfile
import subprocess
from pathlib import Path

# Project Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

ARCHIVE_DIR = PROJECT_ROOT / "01_archive"
SPECS_DIR = PROJECT_ROOT / "03_specs"
CLIPS_DIR = PROJECT_ROOT / "02_clips"
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))

from spec_reader import read_tape_spec
from video_duration import get_video_duration


def parse_timestamp_to_seconds(ts_str: str) -> float:
    """Convert HH:MM:SS.mmm or seconds string to total seconds float."""
    if not ts_str:
        return 0.0
    parts = ts_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts_str)


def parse_timestamp_to_ms(ts_str: str) -> int:
    """Convert timestamp to integer milliseconds for FFmetadata format."""
    return int(parse_timestamp_to_seconds(ts_str) * 1000)


def build_crop_filter(crop_str: str) -> str:
    """
    Convert spec crop 'LEFT RIGHT TOP BOTTOM' into FFmpeg crop filter string.
    FFmpeg crop syntax: crop=out_w:out_h:x:y
    """
    if not crop_str:
        return ""
    parts = crop_str.split()
    if len(parts) == 4:
        left, right, top, bottom = map(int, parts)
        return f"crop=iw-{left}-{right}:ih-{top}-{bottom}:{left}:{top}"
    return ""


def generate_ffmetadata(clip, clip_start_sec: float, total_duration_sec: float) -> str:
    """
    Generates FFmetadata text format for embedding subchapter markers into MP4.
    Timestamps are converted to relative offsets from the clip's start time.
    """
    lines = [";FFMETADATA1", f"title={clip.title}"]
    if clip.date:
        lines.append(f"date={clip.date}")

    clip_start_ms = int(clip_start_sec * 1000)

    for i, sub in enumerate(clip.subchapters):
        sub_start_ms = parse_timestamp_to_ms(sub.start) - clip_start_ms
        
        # Calculate subchapter end time relative to clip start
        if sub.end:
            sub_end_ms = parse_timestamp_to_ms(sub.end) - clip_start_ms
        elif i + 1 < len(clip.subchapters):
            sub_end_ms = parse_timestamp_to_ms(clip.subchapters[i + 1].start) - clip_start_ms
        else:
            sub_end_ms = int(total_duration_sec * 1000) - clip_start_ms

        lines.extend([
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={max(0, sub_start_ms)}",
            f"END={max(0, sub_end_ms)}",
            f"title={sub.title}"
        ])

    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) < 2:
        print("Usage: ./scripts/03_make_clips.py [--frames-only] <TAPE_NAME>")
        sys.exit(1)

    frames_only = "--frames-only" in sys.argv
    tape_args = [arg for arg in sys.argv[1:] if arg != "--frames-only"]

    if not tape_args:
        print("Error: Missing tape name argument.")
        sys.exit(1)

    tape_name = Path(tape_args[0]).stem

    spec_path = SPECS_DIR / f"{tape_name}.txt"
    mkv_path = ARCHIVE_DIR / f"{tape_name}.mkv"

    if not spec_path.exists():
        print(f"Error: Spec file not found at '{spec_path}'")
        sys.exit(1)
    if not mkv_path.exists():
        print(f"Error: Archival MKV not found at '{mkv_path}'")
        sys.exit(1)

    data = read_tape_spec(spec_path.read_text())
    total_duration_str = get_video_duration(str(mkv_path))
    data.resolve_missing_end_times(total_duration_str)
    total_duration_sec = parse_timestamp_to_seconds(total_duration_str)

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    tape_clips_dir = CLIPS_DIR / tape_name
    if frames_only:
        tape_clips_dir.mkdir(exist_ok=True)

    print(f"{'Generating diagnostic frames' if frames_only else 'Encoding clip MP4s'} for: {tape_name}")

    # Process each top-level Clip as ONE output file
    for clip in data.clips:
        start_sec = parse_timestamp_to_seconds(clip.start) if clip.start else 0.0
        
        if clip.end:
            end_sec = parse_timestamp_to_seconds(clip.end)
        else:
            end_sec = total_duration_sec

        duration_sec = end_sec - start_sec
        mid_sec = start_sec + (duration_sec / 2.0)

        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in clip.title).strip().replace(" ", "_")
        clip_prefix = f"{tape_name}_{clip.idx}_{safe_title}"

        # Crop Geometry (Left Right Top Bottom)
        crop_val = clip.crop if clip.crop else data.global_crop
        ffmpeg_crop = build_crop_filter(crop_val)

        if frames_only:
            # Position mappings: 1 = first, 2 = mid, 3 = last
            timestamps = [
                ("1", start_sec),
                ("2", mid_sec),
                ("3", max(start_sec, end_sec - 0.1))
            ]
            
            for num_code, t_sec in timestamps:
                # 'a' = uncropped
                uncropped_out = tape_clips_dir / f"{clip_prefix}_{num_code}a.png"
                cmd_uncropped = [
                    "ffmpeg", "-y", "-loglevel", "warning",
                    "-ss", str(t_sec), "-i", str(mkv_path),
                    "-vframes", "1", str(uncropped_out)
                ]
                subprocess.run(cmd_uncropped, check=True)

                # 'b' = cropped
                if ffmpeg_crop:
                    cropped_out = tape_clips_dir / f"{clip_prefix}_{num_code}b.png"
                    cmd_cropped = [
                        "ffmpeg", "-y", "-loglevel", "warning",
                        "-ss", str(t_sec), "-i", str(mkv_path),
                        "-vf", ffmpeg_crop, "-vframes", "1", str(cropped_out)
                    ]
                    subprocess.run(cmd_cropped, check=True)

            print(f"[{clip.idx}] Captured diagnostic frames (1a/1b, 2a/2b, 3a/3b) for: {clip.title}")
            continue

        # Full MP4 Clip Generation
        output_mp4 = CLIPS_DIR / f"{clip_prefix}.mp4"

        # Build FFmpeg video filters
        vf_chains = ["bwdif=mode=send_field:deint=all"]
        if ffmpeg_crop:
            vf_chains.append(ffmpeg_crop)
        vf_arg = ",".join(vf_chains)

        # Generate temporary FFmetadata file for chapter markers
        ffmeta_content = generate_ffmetadata(clip, start_sec, total_duration_sec)
        
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as meta_file:
            meta_file.write(ffmeta_content)
            meta_path = meta_file.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-loglevel", "warning",
                "-ss", str(start_sec),
                "-to", str(end_sec),
                "-i", str(mkv_path),
                "-i", meta_path,
                "-map_metadata", "1",
                "-vf", vf_arg,
                "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                "-c:a", "aac", "-b:a", "192k",
                str(output_mp4)
            ]

            print(f"Encoding clip [{clip.idx}]: {clip.title} (with {len(clip.subchapters)} embedded chapter markers)...")
            subprocess.run(cmd, check=True)
        finally:
            Path(meta_path).unlink(missing_ok=True)

    print("Done!")


if __name__ == "__main__":
    main()
