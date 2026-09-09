#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom


def convert_txt_to_mkv_xml(basename):
    # Normalize input path: strip .txt or .mkv extension if provided by mistake
    base_path = Path(basename)
    if base_path.suffix in [".txt", ".mkv", ".xml"]:
        base_path = base_path.with_suffix("")

    input_txt = base_path.with_suffix(".txt")
    output_xml = base_path.with_suffix(".xml")
    target_mkv = base_path.with_suffix(".mkv")

    if not input_txt.exists():
        print(f"Error: Input file '{input_txt}' not found.")
        sys.exit(1)

    # 1. Create root XML structure
    chapters = ET.Element("Chapters")
    edition = ET.SubElement(chapters, "EditionEntry")

    with open(input_txt, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip blank lines and comments/reel headers
            if not line or line.startswith("#"):
                continue

            # Split pipe-delimited fields
            parts = [p.strip() for p in line.split("|")]

            # Ensure row has all 8 fields
            if len(parts) >= 8:
                start_time = parts[1]
                end_time = parts[2]
                label = parts[7]

                # Construct ChapterAtom
                atom = ET.SubElement(edition, "ChapterAtom")

                # Add Start Time
                start_elem = ET.SubElement(atom, "ChapterTimeStart")
                start_elem.text = start_time

                # Add End Time
                end_elem = ET.SubElement(atom, "ChapterTimeEnd")
                end_elem.text = end_time

                # Add Display Title
                display = ET.SubElement(atom, "ChapterDisplay")
                title = ET.SubElement(display, "ChapterString")
                title.text = label

    # 2. Pretty-print XML string
    rough_string = ET.tostring(chapters, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    # 3. Write XML file
    with open(output_xml, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"Generated XML: '{output_xml}'")

    # 4. Inject into MKV using mkvpropedit (if MKV exists)
    if target_mkv.exists():
        print(f"Injecting chapters into '{target_mkv}'...")
        cmd = ["mkvpropedit", str(target_mkv), "--chapters", str(output_xml)]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Successfully added chapters to '{target_mkv}'!")
        except FileNotFoundError:
            print(
                "Warning: 'mkvpropedit' command not found in PATH. "
                "Ensure MKVToolNix is installed and accessible."
            )
        except subprocess.CalledProcessError as e:
            print(f"Error executing mkvpropedit:\n{e.stderr}")
    else:
        print(f"Note: Target video file '{target_mkv}' was not found. XML saved for later use.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 txt_to_mkv_chapters.py <basename>")
        print("Example: python3 txt_to_mkv_chapters.py Raisanen-8mm")
        sys.exit(1)

    convert_txt_to_mkv_xml(sys.argv[1])
