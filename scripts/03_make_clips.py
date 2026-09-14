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

  --test, --test-clips Encodes 10-second sample MP4s into the log folder to quickly verify
                      macOS Finder previews and cut quality without full encoding.

  --clean, --clean-log Removes the entire diagnostic directory (<TAPE_NAME>-log) and exits.

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
"""

import sys
import time
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


def format_elapsed_time(seconds: float) -> str:
    """Formats floating-point seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    rem_seconds = seconds % 60
    return f"{minutes}m {rem_seconds:.1f}s"


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


def clean_directory(dir_path: Path, do_uncropped: bool = False, do_cropped: bool = False, frames_mode: bool = False, test_mode: bool = False):
    """Targeted removal of PNG snapshots, test MP4s, and log files based on run mode."""
    if not dir_path.exists():
        return
    for item in dir_path.iterdir():
        if not item.is_file():
            continue
        
        name = item.name.lower()

        # Clear previous test clips when running test mode
        if test_mode and name.endswith("_test.mp4"):
            item.unlink()

        # Clear main log file when running standard full encode
        if not frames_mode and not test_mode and name.endswith(".log"):
            item.unlink()

        # Clear previous 'a.png' files
        if do_uncropped and name.endswith("a.png"):
            item.unlink()

        # Clear previous 'b.png' files
        if do_cropped and name.endswith("b.png"):
            item.unlink()


def main():
    if len(sys.argv) < 2:
        print("Usage: ./scripts/03_make_clips.py [--clean | --test | --uncropped-frames | --cropped-frames | --frames-only] <TAPE_NAME>")
        sys.exit(1)

    do_clean = "--clean" in sys.argv or "--clean-log" in sys.argv
    do_test = "--test" in sys.argv or "--test-clips" in sys.argv
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

    # Handle --clean / --clean-log flag
    if do_clean:
        if tape_log_dir.exists():
            print(f"Removing diagnostic log directory: {tape_log_dir}")
            shutil.rmtree(tape_log_dir)
            print("Clean complete!")
        else:
            print(f"Diagnostic directory '{tape_log_dir}' does not exist. Nothing to clean.")
        sys.exit(0)

    tape_output_dir.mkdir(exist_ok=True)
    tape_log_dir.mkdir(exist_ok=True)

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

    # Clean up previous target images/test clips without affecting preserved counterparts
    clean_directory(tape_log_dir, do_uncropped, do_cropped, frames_mode, do_test)

    log_file_path = tape_log_dir / "ffmpeg_encode.log"

    if do_test:
        print(f"Generating 10-second TEST clips in: {tape_log_dir}")
    elif frames_mode:
        mode_desc = []
        if do_uncropped:
            mode_desc.append("uncropped ('a')")
        if do_cropped:
            mode_desc.append("cropped ('b')")
        print(f"Generating {' and '.join(mode_desc)} diagnostic frames for: {tape_name}")
    else:
        print(f"Encoding full clip MP4s for: {tape_name}")

    print(f"Clips Directory:     {tape_output_dir}")
    print(f"Diagnostics & Logs:  {tape_log_dir}\n")

    tape_start_time = time.perf_counter()

    with open(log_file_path, "a", encoding="utf-8") as log_file:
        for clip in data.clips:
            clip_start_time = time.perf_counter()
            segments = resolve_subsegments(clip, total_duration_sec)
            
            safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in clip.title).strip().replace(" ", "_")
            clip_prefix = f"{tape_name}_{clip.idx}_{safe_title}"

            # Crop Geometry (Left Right Top Bottom)
            crop_val = clip.crop if clip.crop else data.global_crop
            ffmpeg_crop = build_crop_filter(crop_val)

            if frames_mode:
                print(f"[{clip.idx}] Capturing diagnostic frames for: {clip.title}...", end="", flush=True)
                
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
                
                elapsed_str = format_elapsed_time(time.perf_counter() - clip_start_time)
                print(f" Done ({elapsed_str})")
                continue

            # Determine destination output file & time limits
            if do_test:
                output_mp4 = tape_log_dir / f"{clip_prefix}_test.mp4"
            else:
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

            # Apple compatibility flags
            apple_compat_flags = [
                "-pix_fmt", "yuv420p", "-tag:v", "avc1",
                "-color_primaries", "smpte170m", "-color_trc", "smpte170m", "-colorspace", "smpte170m"
            ]

            try:
                if is_gapped or len(segments) > 1:
                    print(f"[{clip.idx}] Encoding {'TEST ' if do_test else ''}concatenated clip: {clip.title}...", end="", flush=True)
                    cmd = ["ffmpeg", "-y", "-loglevel", "warning"]
                    
                    # Fast input-side seeking: -ss / -to BEFORE -i
                    for s_sec, e_sec, _ in segments:
                        cmd.extend(["-ss", str(s_sec)])
                        if do_test:
                            # Clamp segment to max 10 seconds for test mode
                            cmd.extend(["-to", str(min(e_sec, s_sec + 10.0))])
                        else:
                            cmd.extend(["-to", str(e_sec)])
                        cmd.extend(["-i", str(mkv_path)])

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
                        "-c:v", "libx264", "-crf", "22", "-preset", "slow"
                    ])
                    cmd.extend(apple_compat_flags)
                    cmd.extend(["-c:a", "aac", "-b:a", "192k", str(output_mp4)])

                else:
                    clip_start = segments[0][0]
                    if do_test:
                        clip_end = min(segments[-1][1], clip_start + 10.0)
                    else:
                        clip_end = segments[-1][1]

                    print(f"[{clip.idx}] Encoding {'TEST ' if do_test else ''}clip: {clip.title}...", end="", flush=True)
                    
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
                        "-c:v", "libx264", "-crf", "22", "-preset", "slow"
                    ]
                    cmd.extend(apple_compat_flags)
                    cmd.extend(["-c:a", "aac", "-b:a", "192k", str(output_mp4)])

                log_file.write(f"\n--- Encoding Clip [{clip.idx}]: {clip.title} {'(TEST)' if do_test else ''} ---\n")
                log_file.flush()
                subprocess.run(cmd, stdout=log_file, stderr=log_file, check=True)
                
                elapsed_str = format_elapsed_time(time.perf_counter() - clip_start_time)
                print(f" Done ({elapsed_str})")
                log_file.write(f"Completed in {elapsed_str}\n")
            finally:
                Path(meta_path).unlink(missing_ok=True)

    total_elapsed_str = format_elapsed_time(time.perf_counter() - tape_start_time)
    print(f"\nAll operations complete for '{tape_name}' in {total_elapsed_str}!")


if __name__ == "__main__":
    main()
