import dataclasses
from typing import List

# ==========================================
# 1. Internal Format (Data Structures)
# ==========================================

@dataclasses.dataclass
class Subchapter:
    start: str
    end: str
    title: str

@dataclasses.dataclass
class Clip:
    idx: str
    start: str
    end: str
    title: str
    date: str
    crop: str
    subchapters: List[Subchapter] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class ArchiveData:
    global_crop: str
    raw_spec: str
    clips: List[Clip] = dataclasses.field(default_factory=list)

# ==========================================
# 2. The Parser Logic
# ==========================================

def parse_tape_spec(text_content: str) -> ArchiveData:
    global_crop = ""
    clips = []
    
    current_clip = None
    is_uncut_mode = False
    
    lines = text_content.splitlines()
    
    for line in lines:
        stripped = line.strip()
        
        # 1. Handle Global Directives and Comments
        if stripped.startswith("## Crop:"):
            global_crop = stripped.replace("## Crop:", "").strip()
            continue
        if not stripped or stripped.startswith("#"):
            continue
            
        # 2. Safely split by pipe (max 5 splits = 6 columns)
        # This solves the "26|10|8|8" bug by keeping extra pipes in the 6th column
        parts = [p.strip() for p in stripped.split('|', 5)]
        
        idx   = parts[0] if len(parts) > 0 else ""
        start = parts[1] if len(parts) > 1 else ""
        end   = parts[2] if len(parts) > 2 else ""
        title = parts[3] if len(parts) > 3 else ""
        date  = parts[4] if len(parts) > 4 else ""
        crop  = parts[5] if len(parts) > 5 else ""

        # 3. Detect Uncut Master Tape Header (Blank IDX)
        if idx == "" and not current_clip and not is_uncut_mode:
            is_uncut_mode = True
            current_clip = Clip(idx="MASTER", start=start, end=end, title=title, date=date, crop=crop)
            clips.append(current_clip)
            continue
            
        # 4. Handle Subchapters for Uncut Master Tape
        if is_uncut_mode:
            sub = Subchapter(idx=idx, start=start, end=end, title=title)
            current_clip.subchapters.append(sub)
            continue
            
        # 5. Handle Cut-Tape Mode
        if "." in idx:
            # It is a decimal subchapter (e.g., 01.01) attached to the current clip
            sub = Subchapter(idx=idx, start=start, end=end, title=title)
            if current_clip:
                current_clip.subchapters.append(sub)
        else:
            # It is a brand new standalone clip (e.g., 01, 02)
            current_clip = Clip(idx=idx, start=start, end=end, title=title, date=date, crop=crop)
            clips.append(current_clip)

    # ==========================================
    # 3. Post-Processing (Chaining & Inheritance)
    # ==========================================
    
    # A. Flatten the sequence to apply Auto-Chaining to missing 'END' times
    chronological_sequence = []
    for clip in clips:
        if clip.subchapters:
            chronological_sequence.extend(clip.subchapters)
        else:
            chronological_sequence.append(clip)
            
    for i in range(len(chronological_sequence) - 1):
        if not chronological_sequence[i].end:
            # Auto-chain: My end time is the next item's start time
            chronological_sequence[i].end = chronological_sequence[i+1].start

    # B. Inherit Missing Dates/Crops & Sync Parent Boundaries
    last_date = ""
    last_crop = global_crop
    
    for clip in clips:
        # Cascade missing metadata downwards
        clip.date = clip.date if clip.date else last_date
        clip.crop = clip.crop if clip.crop else last_crop
        last_date = clip.date
        last_crop = clip.crop
        
        # If the clip has subchapters, the clip's boundaries are defined by them
        if clip.subchapters:
            clip.start = clip.subchapters[0].start
            clip.end = clip.subchapters[-1].end

    return ArchiveData(
        global_crop=global_crop,
        raw_spec=text_content.strip(),
        clips=clips
    )
