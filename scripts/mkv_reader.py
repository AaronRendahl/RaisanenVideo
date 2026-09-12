import json
import subprocess
from models import ArchiveData, Clip, Subchapter


def format_ffprobe_timestamp(seconds_str: str) -> str:
    """Converts ffprobe time in seconds to HH:MM:SS.mmm format."""
    try:
        total_seconds = float(seconds_str)
    except (ValueError, TypeError):
        return "00:00:00.000"

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def read_mkv_metadata(mkv_path: str) -> ArchiveData:
    """Reads chapters, clip dates, and native video track crop fields from an MKV file via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_chapters",
        "-show_streams",
        mkv_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(result.stdout)

    # Reconstruct native crop string from video stream properties
    global_crop = ""
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video":
            top = stream.get("crop_top", 0)
            bottom = stream.get("crop_bottom", 0)
            left = stream.get("crop_left", 0)
            right = stream.get("crop_right", 0)

            if any([top, bottom, left, right]):
                global_crop = f"{top}|{bottom}|{left}|{right}"
            break

    raw_chapters = probe_data.get("chapters", [])
    clips = []

    for idx, chap in enumerate(raw_chapters, start=1):
        chap_tags = chap.get("tags", {})
        title = chap_tags.get("title", f"Clip {idx}")
        date = chap_tags.get("DATE_RECORDED", "")

        start_time = format_ffprobe_timestamp(chap.get("start_time", "0"))
        end_time = format_ffprobe_timestamp(chap.get("end_time", "0"))

        clip_idx = f"{idx:02d}"

        clip = Clip(
            idx=clip_idx,
            start=start_time,
            end=end_time,
            title=title,
            date=date,
            crop=global_crop,
        )
        clips.append(clip)

    return ArchiveData(
        global_crop=global_crop,
        raw_spec="",
        clips=clips,
    )
