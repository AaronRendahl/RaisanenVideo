#!/usr/bin/env python3
"""
03_make_clips.py

Generates web-ready MP4 derivative clips from clean Matroska (.mkv) archival versions.
Processes clip bounds, applies subchapter markers, handles gap splicing, and extracts
diagnostic frame snapshots for cut and crop validation.

Usage:
  ./scripts/03_make_clips.py [FLAGS] <TAPE_NAME>

Flags:
  --uncropped-frames  Extracts uncropped PNG snapshots ('a.png') for crop evaluation.
                      Clears previous 'a.png' files; leaves 'b.png' intact.

  --cropped-frames    Extracts cropped PNG snapshots ('b.png') using current spec crop parameters.
                      Clears previous 'b.png' files; leaves 'a.png' intact for side-by-side review.

  --frames-only       Shortcut flag to generate both uncropped ('a') and cropped ('b') PNG snapshots.

  --clean, --clean-log Wipes all PNG snapshots and log files in the diagnostic directory and exits.

  (No Flags)          Runs full derivative clip MP4 encoding pipeline. Does not extract PNGs.

Directory Structure:
  Input Archival:     01_archive/<TAPE_NAME>.mkv
  Input Spec:         03_specs/<TAPE_NAME>.txt
  Output Clips:       02_clips/<TAPE_NAME>/<TAPE_NAME>_<CLIP_IDX>_<TITLE>.mp4
  Diagnostics & Log:  02_clips/<TAPE_NAME>-log/

Diagnostic Frame Naming Convention:
  <TAPE>_<CLIP_IDX>_<TITLE>_<SUBCHAPTER_IDX>-<POSITION><a|b>.png

  Positions:  1 = Subchapter Start
              2 = Subchapter Midpoint
              3 = Subchapter End

  Variants:   a = Uncropped frame
              b = Cropped frame

  Example:    Raisanen-1987a_01_First_Videos_1-1a.png (Subchapter 1, start frame, uncropped)
              Raisanen-1987a_01_First_Videos_1-1b.png (Subchapter 1, start frame, cropped)
"""

import sys
import shutil
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


def resolve_subsegments(clip, total_duration_sec: float):
    """
    Returns a list of active subsegment tuples: (start_sec, end_sec, title)
    """
    segments = []
    if clip.subchapters:
        for i, sub in enumerate(clip.subchapters):
            s_sec = parse_timestamp_to_seconds(sub.start)
            if sub.end:
                e_sec = parse_timestamp_to_seconds(sub.end)
            elif i + 1 < len(clip.subchapters):
                e_sec = parse_timestamp_to_seconds(clip.subchapters[i + 1].start)
            else:
                e_sec = parse_timestamp_to_seconds(clip.end) if clip.end else total_duration_sec
            segments.append((s_sec, e_sec, sub.title))
    else:
        s_sec = parse_timestamp_to_seconds(clip.start) if clip.start else 0.0
        e_sec = parse_timestamp_to_seconds(clip.end) if clip.end else total_duration_sec
        segments.append((s_sec, e_sec, clip.title))
    return segments


def has_gaps(segments) -> bool:
    """
    Check if there are gaps between segments (threshold = 0.001s / 1ms).
    """
    if len(segments) <= 1:
        return False
    for i in range(len(segments) - 1):
        gap = segments[i + 1][0] - segments[i][1]
        if gap > 0.001:
            return True
    return False


def generate_concat_ffmetadata(clip, segments) -> str:
    """
    Generates FFmetadata text format where subchapter markers are shifted to map
    to the newly concatenated timeline.
    """
    lines = [";FFMETADATA1", f"title={clip.title}"]
    if clip.date:
        lines.append(f"date={clip.date}")

    current_timeline_ms = 0

    for s_sec, e_sec, sub_title in segments:
        duration_ms = int((e_sec - s_sec) * 1000)
        start_ms = current_timeline_ms
        end_ms = current_timeline_ms + duration_ms

        lines.extend([
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start_ms}",
            f"END={end_ms}",
            f"title={sub_title}"
        ])

        current_timeline_ms = end_ms

    return "\n".join(lines) + "\n"


def clean_directory(dir_path: Path, do_uncropped: bool = False, do_cropped: bool = False, frames_mode: bool = False, clean_all: bool = False):
    """Targeted removal of PNG snapshots and log files based on run mode."""
    if not dir_path.exists():
        return
    for item in dir_path.iterdir():
        if not item.is_file():
            continue
        
        name = item.name.lower()
        
        if clean_all:
            if name.endswith(".png") or name.endswith(".log"):
                item.unlink()
            continue

        # If running full encode, clear log file
        if not frames_mode and name.endswith(".log"):
            item.unlink()

        # If generating uncropped frames ('a.png'), wipe previous 'a.png' files
        if do_uncropped and name.endswith("a.png"):
            item.unlink()

        # If generating cropped frames ('b.png'), wipe previous 'b.png' files
        if do_cropped and name.endswith("b.png"):
            item.unlink()


def main():
    if len(sys.argv) < 2:
        print("Usage: ./scripts/03_make_clips.py [--clean | --uncropped-frames | --cropped-frames | --frames-only] <TAPE_NAME>")
        sys.exit(1)

    do_clean = "--clean" in sys.argv or "--clean-log" in sys.argv
    do_uncropped = "--uncropped-frames" in sys.argv or "--frames-only" in sys.argv
    do_cropped = "--cropped-frames" in sys.argv or "--frames-only" in sys.argv
    frames_mode = do_uncropped or do_cropped

    tape_args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    if not tape_args:
        print("Error: Missing tape name argument.")
        sys.exit(1)

    tape_name = Path(tape_args[0]).stem

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Directory setup
    tape_output_dir = CLIPS_DIR / tape_name
    tape_log_dir = CLIPS_DIR / f"{tape_name}-log"

    tape_output_dir.mkdir(exist_ok=True)
    tape_log_dir.mkdir(exist_ok=True)

    # Handle --clean flag
    if do_clean:
        print(f"Cleaning diagnostic directory: {tape_log_dir}")
        clean_directory(tape_log_dir, clean_all=True)
        print("Clean complete!")
        sys.exit(0)

    spec_path = SPECS_DIR / f"{tape_name}.txt"
    mkv_path = ARCHIVE_DIR / f"{tape_name}.mkv"

    if not spec_path.exists():
        print(f"Error: Spec file not found at '{spec_path}'")
        sys.exit(1)
    if not mkv_path.exists():
        print(f"Error: Archival version not found at '{mkv_path}'")
        sys.exit(1)

    data = read_tape_spec(spec_path.read_text())
    total_duration_str = get_video_duration(str(mkv_path))
    data.resolve_missing_end_times(total_duration_str)
    total_duration_sec = parse_timestamp_to_seconds(total_duration_str)

    # Clean up previous target images without affecting preserved counterparts
    clean_directory(tape_log_dir, do_uncropped, do_cropped, frames_mode)

    log_file_path = tape_log_dir / "ffmpeg_encode.log"

    if frames_mode:
        mode_desc = []
        if do_uncropped:
            mode_desc.append("uncropped ('a')")
        if do_cropped:
            mode_desc.append("cropped ('b')")
        print(f"Generating {' and '.join(mode_desc)} diagnostic frames for: {tape_name}")
    else:
        print(f"Encoding clip MP4s for: {tape_name}")

    print(f"Clips Directory:     {tape_output_dir}")
    print(f"Diagnostics & Logs:  {tape_log_dir}")

    with open(log_file_path, "a", encoding="utf-8") as log_file:
        for clip in data.clips:
            segments = resolve_subsegments(clip, total_duration_sec)
            
            safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in clip.title).strip().replace(" ", "_")
            clip_prefix = f"{tape_name}_{clip.idx}_{safe_title}"

            # Crop Geometry (Left Right Top Bottom)
            crop_val = clip.crop if clip.crop else data.global_crop
            ffmpeg_crop = build_crop_filter(crop_val)

            if frames_mode:
                print(f"[{clip.idx}] Capturing per-subchapter diagnostic frames for: {clip.title}")
                
                # Iterate over every subchapter segment
                for sub_idx, (s_sec, e_sec, sub_title) in enumerate(segments, start=1):
                    mid_sec = s_sec + ((e_sec - s_sec) / 2.0)
                    end_sec = max(s_sec, e_sec - 0.1)

                    # Subchapter positions: 1=start, 2=mid, 3=end
                    timestamps = [("1", s_sec), ("2", mid_sec), ("3", end_sec)]
                    
                    for pos_code, t_sec in timestamps:
                        snapshot_prefix = f"{clip_prefix}_{sub_idx}-{pos_code}"
                        
                        # Uncropped snapshot (a)
                        if do_uncropped:
                            uncropped_out = tape_log_dir / f"{snapshot_prefix}a.png"
                            cmd_uncropped = [
                                "ffmpeg", "-y", "-loglevel", "warning",
                                "-ss", str(t_sec), "-i", str(mkv_path),
                                "-vf", "format=rgb24",
                                "-vframes", "1", "-update", "1", 
                                "-sws_flags", "fast_bilinear",
                                str(uncropped_out)
                            ]
                            subprocess.run(cmd_uncropped, stdout=log_file, stderr=log_file, check=True)

                        # Cropped snapshot (b)
                        if do_cropped:
                            if ffmpeg_crop:
                                cropped_out = tape_log_dir / f"{snapshot_prefix}b.png"
                                cmd_cropped = [
                                    "ffmpeg", "-y", "-loglevel", "warning",
                                    "-ss", str(t_sec), "-i", str(mkv_path),
                                    "-vf", f"{ffmpeg_crop},format=rgb24", 
                                    "-vframes", "1", "-update", "1", 
                                    str(cropped_out)
                                ]
                                subprocess.run(cmd_cropped, stdout=log_file, stderr=log_file, check=True)
                            else:
                                print(f"  Notice: No crop parameters set for clip {clip.idx}; skipping 'b' frame.")
                continue

            output_mp4 = tape_output_dir / f"{clip_prefix}.mp4"
            is_gapped = has_gaps(segments)

            # Common video filter setup
            vf_base = "bwdif=mode=send_field:deint=all"
            if ffmpeg_crop:
                vf_base += f",{ffmpeg_crop}"

            # Build metadata file
            ffmeta_content = generate_concat_ffmetadata(clip, segments)
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as meta_file:
                meta_file.write(ffmeta_content)
                meta_path = meta_file.name

            try:
                if is_gapped or len(segments) > 1:
                    print(f"Encoding clip [{clip.idx}]: {clip.title} ({len(segments)} segments concatenated)...")
                    cmd = ["ffmpeg", "-y", "-loglevel", "warning"]
                    
                    # Fast input-side seeking: -ss / -to BEFORE -i
                    for s_sec, e_sec, _ in segments:
                        cmd.extend(["-ss", str(s_sec), "-to", str(e_sec), "-i", str(mkv_path)])

                    filter_lines = []
                    for idx in range(len(segments)):
                        filter_lines.append(f"[{idx}:v]{vf_base}[v{idx}];")
                        filter_lines.append(f"[{idx}:a]anull[a{idx}];")
                    
                    concat_inputs = "".join(f"[v{idx}][a{idx}]" for idx in range(len(segments)))
                    filter_lines.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[outv][outa]")
                    
                    meta_idx = len(segments)
                    cmd.extend([
                        "-i", meta_path,
                        "-filter_complex", "".join(filter_lines),
                        "-map", "[outv]",
                        "-map", "[outa]",
                        "-map_metadata", f"{meta_idx}",
                        "-map_chapters", f"{meta_idx}",
                        "-movflags", "+faststart",
                        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                        "-c:a", "aac", "-b:a", "192k",
                        str(output_mp4)
                    ])
                else:
                    clip_start = segments[0][0]
                    clip_end = segments[-1][1]
                    print(f"Encoding clip [{clip.idx}]: {clip.title} (single-pass encode)...")
                    
                    # Fast input-side seeking: -ss / -to BEFORE -i
                    cmd = [
                        "ffmpeg", "-y", "-loglevel", "warning",
                        "-ss", str(clip_start),
                        "-to", str(clip_end),
                        "-i", str(mkv_path),
                        "-i", meta_path,
                        "-map_metadata", "1",
                        "-map_chapters", "1",
                        "-movflags", "+faststart",
                        "-vf", vf_base,
                        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                        "-c:a", "aac", "-b:a", "192k",
                        str(output_mp4)
                    ]

                log_file.write(f"\n--- Encoding Clip [{clip.idx}]: {clip.title} ---\n")
                log_file.flush()
                subprocess.run(cmd, stdout=log_file, stderr=log_file, check=True)
            finally:
                Path(meta_path).unlink(missing_ok=True)

    print("Done!")


if __name__ == "__main__":
    main()
