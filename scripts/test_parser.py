import sys
from pathlib import Path
from pprint import pprint

# Import the parser and data models from tape_parser.py
from tape_parser import parse_tape_spec, ArchiveData


def run_tests(file_paths):
    for path_str in file_paths:
        path = Path(path_str)
        print("=" * 60)
        print(f" TESTING FILE: {path.name}")
        print("=" * 60)

        if not path.is_file():
            print(f" Error: File not found at '{path}'\n")
            continue

        try:
            content = path.read_text(encoding="utf-8")
            data = parse_tape_spec(content)

            print(f"Global Crop: {data.global_crop!r}")
            print(f"Total Clips Parsed: {len(data.clips)}\n")

            for clip in data.clips:
                print(f"  Clip [{clip.idx}] '{clip.title}'")
                print(f"    Start: {clip.start} | End: {clip.end}")
                print(f"    Date:  {clip.date} | Crop: {clip.crop}")
                if clip.subchapters:
                    print(f"    Subchapters ({len(clip.subchapters)}):")
                    for sub in clip.subchapters:
                        print(
                            f"      - [{sub.idx}] {sub.start} -> {sub.end} | '{sub.title}'"
                        )
                print("-" * 40)
            print("\n")

        except Exception as e:
            print(f" Parsing Failed: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Pass files via CLI: python test_parser.py file1.txt file2.txt ...
        run_tests(sys.argv[1:])
    else:
        # Auto-discover all .txt files in current directory
        txt_files = sorted(list(Path(".").glob("*.txt")))
        if txt_files:
            run_tests([str(f) for f in txt_files])
        else:
            print("No .txt files specified and none found in current directory.")
            print("Usage: python test_parser.py file1.txt file2.txt ...")
