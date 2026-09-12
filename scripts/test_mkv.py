import sys
from pathlib import Path

from mkv_writer import generate_mkv_chapters_and_tags
from spec_reader import read_tape_spec
from spec_writer import write_tape_spec


def run_mkv_test(file_path: str):
    path = Path(file_path)
    print("=" * 65)
    print(f" TESTING MKV METADATA GENERATION: {path.name}")
    print("=" * 65)

    if not path.is_file():
        print(f" Error: Spec file not found at '{path}'\n")
        return

    try:
        # 1. Parse text spec into ArchiveData
        original_text = path.read_text(encoding="utf-8")
        parsed_data = read_tape_spec(original_text)

        # 2. Print any parser warnings
        parsed_data.print_warnings()

        print(f"[SPEC READ] Global Crop: {parsed_data.global_crop!r}")
        print(f"[SPEC READ] Total Clips: {len(parsed_data.clips)}\n")

        # 3. Generate Matroska XMLs (Chapters & Tags)
        chapters_xml, tags_xml = generate_mkv_chapters_and_tags(parsed_data)

        print("~" * 20 + " GENERATED CHAPTERS XML " + "~" * 20)
        print(chapters_xml.rstrip())
        print("~" * 64 + "\n")

        print("~" * 22 + " GENERATED TAGS XML " + "~" * 22)
        print(tags_xml.rstrip())
        print("~" * 64 + "\n")

        # 4. Serialize back to text spec
        recreated_spec_text = write_tape_spec(parsed_data)

        print("~" * 18 + " RECONSTRUCTED TEXT SPEC " + "~" * 18)
        print(recreated_spec_text.rstrip())
        print("~" * 61 + "\n")

        print(" [PASSED] MKV XML generation completed successfully.\n")

    except Exception as e:
        print(f" Test Failed with exception: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            run_mkv_test(arg)
    else:
        print("Usage: python test_mkv.py <path_to_spec.txt>")
        print("Example: python test_mkv.py ../specs/tape1.txt")
