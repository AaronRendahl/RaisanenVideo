import json
import subprocess
from pathlib import Path
from models import ArchiveData, Clip, Subchapter


def format_ffprobe_timestamp(seconds_str: str) -> str:
    """Converts ffprobe time in seconds (e.g. '5772.666000') to HH:MM:SS.mmm format."""
    try:
        total_seconds = float(seconds_str)
    except (ValueError, TypeError):
        return "00:00:00.000"

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def read_mkv_metadata(mkv_path: str) -> ArchiveData:
    """Reads chapters and global tags from an MKV file via ffprobe and returns ArchiveData."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_chapters",
        "-show_format",
        mkv_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(result.stdout)

    format_info = probe_data.get("format", {})
    global_tags = format_info.get("tags", {})

    # Extract global metadata tags
    global_crop = global_tags.get("CROPPING", "")
    raw_spec = global_tags.get("ARCHIVE_SPEC", "")

    # Parse chapters hierarchy
    raw_chapters = probe_data.get("chapters", [])
    clips = []

    for idx, chap in enumerate(raw_chapters, start=1):
        chap_tags = chap.get("tags", {})
        title = chap_tags.get("title", f"Clip {idx}")

        start_time = format_ffprobe_timestamp(chap.get("start_time", "0"))
        end_time = format_ffprobe_timestamp(chap.get("end_time", "0"))

        clip_idx = f"{idx:02d}"

        # Build clip instance
        clip = Clip(
            idx=clip_idx,
            start=start_time,
            end=end_time,
            title=title,
            date="",
            crop=global_crop,
        )
        clips.append(clip)

    return ArchiveData(
        global_crop=global_crop,
        raw_spec=raw_spec,
        clips=clips,
    )
