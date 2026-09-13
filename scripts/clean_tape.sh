#!/usr/bin/env zsh

OPT_8MM=false

while getopts "8" opt; do
  case "$opt" in
    8) OPT_8MM=true ;;
    ?)
       echo "Usage: $0 [-8] <TAPE_NAME_WITHOUT_EXTENSION>"
       exit 1
       ;;
  esac
done

shift $((OPTIND - 1))

if [[ -z "$1" ]]; then
  echo "Error: No input file specified!"
  echo "Usage: $0 [-8] <TAPE_NAME_WITHOUT_EXTENSION>"
  exit 1
fi

VIDIN="$1"
INPUT_FILE="04_originals/${VIDIN}.mpg"
OUTPUT_FILE="01_archive/${VIDIN}.mkv"

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Error: Input file '$INPUT_FILE' not found!"
  exit 1
fi

if $OPT_8MM; then
  echo ">>> Processing 8mm Film: Losslessly stretching timestamps by 1.5x and stripping audio <<<"

  # --no-audio strips audio stream
  # --sync 0:0,1.5 sets delay=0ms and applies 1.5x speed factor to track 0
  mkvmerge -q -o "$OUTPUT_FILE" --no-audio --sync 0:0,1.5 "$INPUT_FILE"

else
  echo ">>> Processing Standard Video: Lossless remux with original audio <<<"

  mkvmerge -q -o "$OUTPUT_FILE" "$INPUT_FILE"
fi

echo "Done! Pure lossless master file saved to $OUTPUT_FILE"
