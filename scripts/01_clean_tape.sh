#!/usr/bin/env zsh

OPT_8MM=false

while getopts "8" opt; do
  case "$opt" in
    8) OPT_8MM=true ;;
    ?)
       echo "Usage: $0 [-8] <TAPE_NAME_OR_PATH>"
       exit 1
       ;;
  esac
done

shift $((OPTIND - 1))

if [[ -z "$1" ]]; then
  echo "Error: No input file specified!"
  echo "Usage: $0 [-8] <TAPE_NAME_OR_PATH>"
  exit 1
fi

RAW_INPUT="$1"

# 1. Resolve Input File
if [[ -f "$RAW_INPUT" ]]; then
  # Path provided directly via tab completion or explicit argument
  INPUT_FILE="$RAW_INPUT"
elif [[ -f "04_originals/${RAW_INPUT}" ]]; then
  # Found directly inside 04_originals with full filename
  INPUT_FILE="04_originals/${RAW_INPUT}"
elif [[ -f "04_originals/${RAW_INPUT}.mpg" ]]; then
  # Fallback: Bare name provided, append .mpg extension in 04_originals
  INPUT_FILE="04_originals/${RAW_INPUT}.mpg"
else
  echo "Error: Input file not found! Checked:"
  echo "  - $RAW_INPUT"
  echo "  - 04_originals/${RAW_INPUT}"
  echo "  - 04_originals/${RAW_INPUT}.mpg"
  exit 1
fi

# 2. Derive Output File Name (always lands in 01_archive with .mkv extension)
TAPE_NAME="${${INPUT_FILE:t}:r}"
OUTPUT_FILE="01_archive/${TAPE_NAME}.mkv"

if $OPT_8MM; then
  echo ">>> Processing 8mm Film: Losslessly stretching timestamps by 1.5x and stripping audio <<<"
  mkvmerge -q -o "$OUTPUT_FILE" --no-audio --sync 0:0,1.5 "$INPUT_FILE"
else
  echo ">>> Processing Standard Video: Lossless remux with original audio <<<"
  mkvmerge -q -o "$OUTPUT_FILE" "$INPUT_FILE"
fi

echo "Done! Pure lossless master file saved to $OUTPUT_FILE"
