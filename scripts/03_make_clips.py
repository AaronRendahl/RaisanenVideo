#!/usr/bin/env python3
"""
03_make_clips.py

CLI entrypoint to generate derivative MP4 clips (1 continuous file per top-level Clip)
by concatenating active subchapters/segments, removing dead gaps, and embedding
re-aligned MP4 chapter markers.
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

    for clip in data.clips:
        segments = resolve_subsegments(clip, total_duration_sec)
        
        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in clip.title).strip().replace(" ", "_")
        clip_prefix = f"{tape_name}_{clip.idx}_{safe_title}"

        # Crop Geometry (Left Right Top Bottom)
        crop_val = clip.crop if clip.crop else data.global_crop
        ffmpeg_crop = build_crop_filter(crop_val)

        if frames_only:
            # Diagnostics: first frame of first segment, mid of middle segment, last of last segment
            first_sec = segments[0][0]
            mid_seg = segments[len(segments) // 2]
            mid_sec = mid_seg[0] + ((mid_seg[1] - mid_seg[0]) / 2.0)
            last_sec = max(segments[-1][0], segments[-1][1] - 0.1)

            timestamps = [("1", first_sec), ("2", mid_sec), ("3", last_sec)]
            
            for num_code, t_sec in timestamps:
                uncropped_out = tape_clips_dir / f"{clip_prefix}_{num_code}a.png"
                cmd_uncropped = [
                    "ffmpeg", "-y", "-loglevel", "warning",
                    "-ss", str(t_sec), "-i", str(mkv_path),
                    "-vframes", "1", str(uncropped_out)
                ]
                subprocess.run(cmd_uncropped, check=True)

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

        output_mp4 = CLIPS_DIR / f"{clip_prefix}.mp4"

        # Build FFmpeg command with complex filter for segment trimming & concating
        cmd = ["ffmpeg", "-y", "-loglevel", "warning"]
        
        # Add input stream per segment
        for s_sec, e_sec, _ in segments:
            cmd.extend(["-ss", str(s_sec), "-to", str(e_sec), "-i", str(mkv_path)])

        # Build filtergraph
        vf_base = "bwdif=mode=send_field:deint=all"
        if ffmpeg_crop:
            vf_base += f",{ffmpeg_crop}"

        filter_lines = []
        for idx in range(len(segments)):
            filter_lines.append(f"[{idx}:v]{vf_base}[v{idx}];")
            filter_lines.append(f"[{idx}:a]anull[a{idx}];")
        
        concat_inputs = "".join(f"[v{idx}][a{idx}]" for idx in range(len(segments)))
        filter_lines.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[outv][outa]")
        
        filter_complex_str = "".join(filter_lines)

        # Build temporary metadata file
        ffmeta_content = generate_concat_ffmetadata(clip, segments)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as meta_file:
            meta_file.write(ffmeta_content)
            meta_path = meta_file.name

        cmd.extend([
            "-i", meta_path,
            "-filter_complex", filter_complex_str,
            "-map", "[outv]",
            "-map", "[outa]",
            "-map_metadata", f"{len(segments)}",
            "-c:v", "libx264", "-crf", "18", "-preset", "slow",
            "-c:a", "aac", "-b:a", "192k",
            str(output_mp4)
        ])

        try:
            print(f"Encoding clip [{clip.idx}]: {clip.title} ({len(segments)} concatenated segment(s))...")
            subprocess.run(cmd, check=True)
        finally:
            Path(meta_path).unlink(missing_ok=True)

    print("Done!")


if __name__ == "__main__":
    main()
