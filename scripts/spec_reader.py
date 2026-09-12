from models import ArchiveData, Clip, Subchapter


def read_tape_spec(text_content: str) -> ArchiveData:
    global_crop = ""
    clips = []

    current_clip = None
    is_uncut_mode = False

    lines = text_content.splitlines()

    for line in lines:
        stripped = line.strip()

        # 1. Directives & Comments
        if stripped.startswith("## Crop:"):
            global_crop = stripped.replace("## Crop:", "").strip()
            continue
        if not stripped or stripped.startswith("#"):
            continue

        # 2. Pipe splitting (max 5 splits -> 6 columns)
        parts = [p.strip() for p in stripped.split("|", 5)]

        idx = parts[0] if len(parts) > 0 else ""
        start = parts[1] if len(parts) > 1 else ""
        end = parts[2] if len(parts) > 2 else ""
        title = parts[3] if len(parts) > 3 else ""
        date = parts[4] if len(parts) > 4 else ""
        crop = parts[5] if len(parts) > 5 else ""

        # 3. Detect Uncut Master Tape Header (Blank IDX)
        if idx == "" and not current_clip and not is_uncut_mode:
            is_uncut_mode = True
            current_clip = Clip(
                idx="MASTER",
                start=start,
                end=end,
                title=title,
                date=date,
                crop=crop,
            )
            clips.append(current_clip)
            continue

        # 4. Uncut Mode Subchapters
        if is_uncut_mode:
            sub = Subchapter(idx=idx, start=start, end=end, title=title)
            current_clip.subchapters.append(sub)
            continue

        # 5. Cut-Tape Mode
        if "." in idx:
            sub = Subchapter(idx=idx, start=start, end=end, title=title)
            if current_clip:
                current_clip.subchapters.append(sub)
        else:
            current_clip = Clip(
                idx=idx,
                start=start,
                end=end,
                title=title,
                date=date,
                crop=crop,
            )
            clips.append(current_clip)

    # Post-Processing: Auto-Chaining
    chronological_sequence = []
    for clip in clips:
        if clip.subchapters:
            chronological_sequence.extend(clip.subchapters)
        else:
            chronological_sequence.append(clip)

    for i in range(len(chronological_sequence) - 1):
        if not chronological_sequence[i].end:
            chronological_sequence[i].end = chronological_sequence[i + 1].start

    # Post-Processing: Subchapter boundary syncing & Global crop fallbacks
    for clip in clips:
        # Fall back to global crop if no custom crop was defined for this clip
        clip.crop = clip.crop if clip.crop else global_crop

        # Sync parent clip boundaries if subchapters exist
        if clip.subchapters:
            clip.start = clip.subchapters[0].start
            clip.end = clip.subchapters[-1].end

    return ArchiveData(
        global_crop=global_crop, raw_spec=text_content.strip(), clips=clips
    )
