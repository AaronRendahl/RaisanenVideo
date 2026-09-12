import sys
from pathlib import Path

from mkv_writer import generate_mkv_chapters_xml, generate_mkv_tags_xml
from spec_reader import read_tape_spec


def test_mkv_xml_generation(file_path: str):
    path = Path(file_path)
    if not path.is_file():
        print(f"Error: File '{path}' not found.")
        return

    print("=" * 65)
    print(f" TESTING REAL SPEC: {path.name}")
    print("=" * 65)

    # 1. Read real txt spec
    raw_text = path.read_text(encoding="utf-8")
    data = read_tape_spec(raw_text)

    # 2. Print collected warnings if any
    data.print_warnings()

    # 3. Generate Matroska XMLs
    chapters_xml = generate_mkv_chapters_xml(data)
    tags_xml = generate_mkv_tags_xml(data)

    print("\n--- GENERATED MATROSKA CHAPTERS XML ---")
    print(chapters_xml)

    print("--- GENERATED MATROSKA TAGS XML ---")
    print(tags_xml)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_mkv_xml_generation(sys.argv[1])
    else:
        # Automatically pick the first .txt file found in specs directory or current directory
        txt_files = list(Path(".").glob("*.txt")) + list(
            Path("../specs").glob("*.txt")
        )
        if txt_files:
            test_mkv_xml_generation(str(txt_files[0]))
        else:
            print("Usage: python test_mkv.py path/to/your_tape_spec.txt")
