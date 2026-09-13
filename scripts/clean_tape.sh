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

# Configure Audio Stream
if $OPT_8MM; then
  AUDIO_ARG="-an"
else
  AUDIO_ARG="-c:a copy"
fi

echo "Cleaning tape '$INPUT_FILE' -> '$OUTPUT_FILE'..."

ffmpeg -hide_banner -loglevel error -y \
  -fflags +genpts+discardcorrupt \
  -i "$INPUT_FILE" \
  -c:v copy \
  ${=AUDIO_ARG} \
  -max_muxing_queue_size 1024 \
  -avoid_negative_ts make_zero \
  "$OUTPUT_FILE"

echo "Done! File saved to $OUTPUT_FILE"

