# Step 1. Use this script to convert a clean copy
# Step 2. Open with LosslessCut. Convert to supported format if asked.
# Step 3. Find frames to start and end on, and put into cut2.sh
# Step 4. Run cut2.sh

VIDIN="Raisanen-1987.mpg"

ffmpeg -hide_banner -loglevel error -y \
  -fflags +genpts+discardcorrupt \
  -i "${VIDIN}.mpg" \
  -c:v copy \
  -c:a copy \
  -max_muxing_queue_size 1024 \
  -avoid_negative_ts make_zero \
  "${VIDIN}.mkv"

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

ffmpeg -hide_banner -loglevel error -y \
  -fflags +genpts+discardcorrupt \
  -i "${VIDIN}.mpg" \
  -c:v copy \
  -af "aresample=async=1:first_pts=0" \
  -c:a pcm_s16le \
  -max_muxing_queue_size 1024 \
  -avoid_negative_ts make_zero \
  -movflags +faststart \
  "${VIDIN}.mov"

ffmpeg -y -fflags +genpts+discardcorrupt \
  -i "${VIDIN}.mpg" \
  -af "aresample=async=1:first_pts=0" \
  -c:v copy -c:a aac -b:a 192k \
  -max_muxing_queue_size 1024 \
  -avoid_negative_ts make_zero -movflags +faststart \
  "${VIDIN}.mp4"
