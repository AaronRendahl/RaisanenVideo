from models import ArchiveData


def write_tape_spec(data: ArchiveData) -> str:
    lines = []

    # 1. Global Crop
    if data.global_crop:
        lines.append(f"## Crop: {data.global_crop}")
        lines.append("")

    # 2. Mode Check
    is_uncut_mode = len(data.clips) == 1 and data.clips[0].idx in (
        "",
        "MASTER",
    )

    if is_uncut_mode:
        master = data.clips[0]
        crop_field = master.crop if master.crop != data.global_crop else ""
        lines.append(f"|||{master.title}|{master.date}|{crop_field}")

        for sub in master.subchapters:
            lines.append(f"{sub.idx}|{sub.start}|{sub.end}|{sub.title}")

    else:
        for clip in data.clips:
            crop_field = clip.crop if clip.crop != data.global_crop else ""
            lines.append(
                f"{clip.idx}|{clip.start}|{clip.end}|{clip.title}|{clip.date}|{crop_field}"
            )

            for sub in clip.subchapters:
                lines.append(f"{sub.idx}|{sub.start}|{sub.end}|{sub.title}")

    return "\n".join(lines) + "\n"
