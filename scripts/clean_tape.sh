#!/usr/bin/env zsh

# Step 1. Use this script to convert a clean copy
# Step 2. Open with LosslessCut. Convert to supported format if asked.
# Step 3. Find frames to start and end on, and put into tapename.txt
# Step 4. Run process_tape.sh
# Default flag values

OPT_8MM=false
TAPE_DATE=""

# Parse options
while getopts "8d:" opt; do
  case "$opt" in
    8) OPT_8MM=true ;;
    d) TAPE_DATE="$OPTARG" ;;
    ?)
       echo "Usage: $0 [-8] [-d YYYY-MM-DD] <TAPE_NAME_WITHOUT_EXTENSION> [TITLE]"
       exit 1
       ;;
  esac
done

shift $((OPTIND - 1))

if [[ -z "$1" ]]; then
  echo "Error: No input file specified!"
  echo "Usage: $0 [-8] [-d YYYY-MM-DD] <TAPE_NAME_WITHOUT_EXTENSION> [TITLE]"
  exit 1
fi

VIDIN="$1"
TAPE_TITLE="$2"
INPUT_FILE="${VIDIN}.mpg"
OUTPUT_FILE="${VIDIN}.mkv"

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

# Build Metadata Array
METADATA_ARGS=()

if [[ -n "$TAPE_TITLE" ]]; then
  echo ">>> Embedding Title Metadata: \"$TAPE_TITLE\" <<<"
  METADATA_ARGS+=(-metadata "title=$TAPE_TITLE")
fi

if [[ -n "$TAPE_DATE" ]]; then
  echo ">>> Embedding Date Metadata: \"$TAPE_DATE\" <<<"
  METADATA_ARGS+=(-metadata "date=$TAPE_DATE" -metadata "creation_time=$TAPE_DATE")
fi

echo "Cleaning tape '$INPUT_FILE' -> '$OUTPUT_FILE'..."

ffmpeg -hide_banner -loglevel error -y \
  -fflags +genpts+discardcorrupt \
  -i "$INPUT_FILE" \
  -c:v copy \
  ${=AUDIO_ARG} \
  "${METADATA_ARGS[@]}" \
  -max_muxing_queue_size 1024 \
  -avoid_negative_ts make_zero \
  "$OUTPUT_FILE"

echo "Done! File saved to $OUTPUT_FILE"

# .mkv — "True Archival Purist" Master:
# Preserves both video and audio bit-for-bit (mpeg2video + MP2). Strips the
# fragile .mpg container and resets timestamps to t=0 for frame-accurate
# logging in LosslessCut. Best for untouched archiving.

# .mov — "macOS Integrated" Master:
# Keeps video bit-exact while decoding audio to raw, uncompressed PCM.
# 100% loss-free audio quality, perfectly synced, and natively playable in
# QuickTime and macOS Finder previews (at the cost of larger file size).

# .mp4 — "Universally Compatible" Master:
# Keeps video bit-exact but re-encodes audio once to high-bitrate AAC.
# Plays natively on any device or OS. Allows Phase 2 to stream-copy (-c:a copy)
# the audio without a second lossy re-encode.

# ffmpeg -hide_banner -loglevel error -y \
#   -fflags +genpts+discardcorrupt \
#   -i "${VIDIN}.mpg" \
#   -c:v copy \
#   -af "aresample=async=1:first_pts=0" \
#   -c:a pcm_s16le \
#   -max_muxing_queue_size 1024 \
#   -avoid_negative_ts make_zero \
#   -movflags +faststart \
#   "${VIDIN}.mov"
#
# ffmpeg -y -fflags +genpts+discardcorrupt \
#   -i "${VIDIN}.mpg" \
#   -af "aresample=async=1:first_pts=0" \
#   -c:v copy -c:a aac -b:a 192k \
#   -max_muxing_queue_size 1024 \
#   -avoid_negative_ts make_zero -movflags +faststart \
#   "${VIDIN}.mp4"
