from tape_parser import ArchiveData

def write_tape_spec(data: ArchiveData) -> str:
    lines = []
    
    # 1. Output Global Crop directive if present
    if data.global_crop:
        lines.append(f"## Crop: {data.global_crop}")
        lines.append("")  # Blank line separator
        
    # 2. Check if this is an Uncut Master Tape
    # (Triggered when there is exactly 1 clip with idx "MASTER" or blank idx)
    is_uncut_mode = len(data.clips) == 1 and data.clips[0].idx in ("", "MASTER")

    if is_uncut_mode:
        master = data.clips[0]
        # Output the blank IDX header row: |||TITLE|DATE|CROP
        # Only output crop if it differs from global_crop
        crop_field = master.crop if master.crop != data.global_crop else ""
        lines.append(f"|||{master.title}|{master.date}|{crop_field}")
        
        # Output subchapters as plain integer rows (1, 2, 3...)
        for sub in master.subchapters:
            lines.append(f"{sub.idx}|{sub.start}|{sub.end}|{sub.title}")
            
    else:
        # Cut-Tape Mode (Multiple clips or explicit clip indices)
        for clip in data.clips:
            # Only output crop if it differs from global_crop
            crop_field = clip.crop if clip.crop != data.global_crop else ""
            
            # Clip header row: IDX|START|END|TITLE|DATE|CROP
            lines.append(f"{clip.idx}|{clip.start}|{clip.end}|{clip.title}|{clip.date}|{crop_field}")
            
            # Output attached subchapters (e.g., 01.01, 01.02)
            for sub in clip.subchapters:
                lines.append(f"{sub.idx}|{sub.start}|{sub.end}|{sub.title}")

    return "\n".join(lines) + "\n"
