import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
from models import ArchiveData, Clip, Subchapter


def format_mkv_timestamp(ts: str) -> str:
    """Converts HH:MM:SS.mmm or HH:MM:SS to Matroska HH:MM:SS.nanoseconds format."""
    if not ts:
        return "00:00:00.000000000"
    
    parts = ts.split(".")
    time_part = parts[0]
    
    # Standardize time components
    t_parts = time_part.split(":")
    if len(t_parts) == 2:
        time_part = f"00:{t_parts[0]}:{t_parts[1]}"
    
    ms_part = parts[1] if len(parts) > 1 else "0"
    ms_padded = ms_part.ljust(9, '0')[:9]
    
    return f"{time_part}.{ms_padded}"


def generate_mkv_chapters_xml(data: ArchiveData) -> str:
    """Generates standard Matroska XML chapter string from ArchiveData."""
    root = ET.Element("Chapters")
    edition = ET.SubElement(root, "EditionEntry")
    
    # Flag as default edition
    ET.SubElement(edition, "EditionFlagDefault").text = "1"
    
    for clip in data.clips:
        clip_atom = ET.SubElement(edition, "ChapterAtom")
        ET.SubElement(clip_atom, "ChapterTimeStart").text = format_mkv_timestamp(clip.start)
        if clip.end:
            ET.SubElement(clip_atom, "ChapterTimeEnd").text = format_mkv_timestamp(clip.end)
        
        display = ET.SubElement(clip_atom, "ChapterDisplay")
        ET.SubElement(display, "ChapterString").text = clip.title
        ET.SubElement(display, "ChapterLanguage").text = "eng"
        
        # Add Subchapters as child ChapterAtoms
        for sub in clip.subchapters:
            sub_atom = ET.SubElement(clip_atom, "ChapterAtom")
            ET.SubElement(sub_atom, "ChapterTimeStart").text = format_mkv_timestamp(sub.start)
            if sub.end:
                ET.SubElement(sub_atom, "ChapterTimeEnd").text = format_mkv_timestamp(sub.end)
            
            sub_display = ET.SubElement(sub_atom, "ChapterDisplay")
            ET.SubElement(sub_display, "ChapterString").text = sub.title
            ET.SubElement(sub_display, "ChapterLanguage").text = "eng"

    raw_xml = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(raw_xml)
    return parsed.toprettyxml(indent="  ")


def generate_mkv_tags_xml(data: ArchiveData) -> str:
    """Generates Matroska XML tags string for global tape metadata."""
    root = ET.Element("Tags")
    
    # Global / Movie level tag target (TargetTypeValue 50 = MOVIE/TAPE)
    tag = ET.SubElement(root, "Tag")
    targets = ET.SubElement(tag, "Targets")
    ET.SubElement(targets, "TargetTypeValue").text = "50"
    
    # Global Crop Tag if present
    if data.global_crop:
        simple = ET.SubElement(tag, "Simple")
        ET.SubElement(simple, "name").text = "CROPPING"
        ET.SubElement(simple, "string").text = data.global_crop
        
    # Embed raw archive spec text as custom tag for full provenance
    if data.raw_spec:
        simple = ET.SubElement(tag, "Simple")
        ET.SubElement(simple, "name").text = "ARCHIVE_SPEC"
        ET.SubElement(simple, "string").text = data.raw_spec

    raw_xml = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(raw_xml)
    return parsed.toprettyxml(indent="  ")


def write_mkv_metadata(mkv_path: str, data: ArchiveData) -> None:
    """In-place updates an MKV file's chapters and tags using mkvpropedit."""
    chapters_xml = generate_mkv_chapters_xml(data)
    tags_xml = generate_mkv_tags_xml(data)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        chap_file = os.path.join(tmpdir, "chapters.xml")
        tags_file = os.path.join(tmpdir, "tags.xml")
        
        with open(chap_file, "w", encoding="utf-8") as f:
            f.write(chapters_xml)
            
        with open(tags_file, "w", encoding="utf-8") as f:
            f.write(tags_xml)
            
        cmd = [
            "mkvpropedit",
            mkv_path,
            "--chapters", chap_file,
            "--tags", f"global:{tags_file}"
        ]
        
        print(f"Applying metadata to {mkv_path} via mkvpropedit...")
        subprocess.run(cmd, check=True)
        print(" Successfully wrote chapters and tags to MKV container.")
