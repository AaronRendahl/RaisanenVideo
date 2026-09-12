import sys
from pathlib import Path

from models import ArchiveData
from spec_reader import read_tape_spec
from spec_writer import write_tape_spec


def run_spec_tests(file_paths):
    for path_str in file_paths:
        path = Path(path_str)
        print("=" * 65)
        print(f" TESTING SPEC FILE: {path.name}")
        print("=" * 65)

        if not path.is_file():
            print(f" Error: File not found at '{path}'\n")
            continue

        try:
            # -------------------------------------------------------------
            # STEP 1: Test Reading (txt -> ArchiveData)
            # -------------------------------------------------------------
            original_text = path.read_text(encoding="utf-8")
            parsed_data = read_tape_spec(original_text)

            print(f"[READ TEST] Global Crop: {parsed_data.global_crop!r}")
            print(f"[READ TEST] Total Clips Parsed: {len(parsed_data.clips)}\n")

            for clip in parsed_data.clips:
                print(f"  Clip [{clip.idx}] '{clip.title}'")
                print(f"    Start: {clip.start} | End: {clip.end}")
                print(f"    Date:  {clip.date} | Crop: {clip.crop}")
                if clip.subchapters:
                    print(f"    Subchapters ({len(clip.subchapters)}):")
                    for sub in clip.subchapters:
                        print(
                            f"      - [{sub.idx}] {sub.start} -> {sub.end} | '{sub.title}'"
                        )
                print("-" * 45)

            # -------------------------------------------------------------
            # STEP 2: Test Writing (ArchiveData -> txt)
            # -------------------------------------------------------------
            generated_text = write_tape_spec(parsed_data)

            print("\n" + "~" * 20 + " GENERATED TEXT SPEC " + "~" * 20)
            print(generated_text.rstrip())
            print("~" * 61 + "\n")

            # -------------------------------------------------------------
            # STEP 3: Round-Trip Verification
            # Parse the regenerated text to verify data symmetry
            # -------------------------------------------------------------
            roundtrip_data = read_tape_spec(generated_text)

            # Ignore raw_spec string comparison, compare structured clips
            parsed_clips_repr = repr(parsed_data.clips)
            roundtrip_clips_repr = repr(roundtrip_data.clips)

            if parsed_clips_repr == roundtrip_clips_repr:
                print(" [PASSED] Round-trip verification successful!")
            else:
                print(" [FAILED] Data mismatch after round-trip conversion!")

            # -------------------------------------------------------------
            # STEP 4: Print Warnings at the Bottom of Output
            # -------------------------------------------------------------
            if parsed_data.warnings:
                print("\n--- Parsed Spec Warnings ---")
                parsed_data.print_warnings()

            # Note: Round-trip warnings will usually be empty because write_tape_spec
            # strips invalid subchapter dates/crops during serialization.
            if roundtrip_data.warnings:
                print("\n--- Recreated Spec Warnings ---")
                roundtrip_data.print_warnings()

            print("\n")

        except Exception as e:
            print(f" Test Failed with exception: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Pass file paths via command-line arguments
        run_spec_tests(sys.argv[1:])
    else:
        # Fall back to finding any .txt files in current directory or ../specs
        search_dirs = [Path("."), Path("../specs"), Path("./specs")]
        txt_files = []
        for d in search_dirs:
            if d.exists():
                txt_files.extend(sorted(list(d.glob("*.txt"))))

        if txt_files:
            run_spec_tests([str(f) for f in txt_files])
        else:
            print(
                "No .txt files specified and none found in default directories."
            )
            print("Usage: python test_spec.py path/to/spec.txt")
