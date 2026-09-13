#!/usr/bin/env zsh

OPT_8MM=false

# Parse options
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
