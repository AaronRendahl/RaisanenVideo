VIDIN="Raisanen-1987a"

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

# ## alternate option, could make a new mp4 but this would reencode the audio
# ffmpeg -y -fflags +genpts+discardcorrupt \
#   -i Raisanen-1987a.mpg \
#   -af "aresample=async=1:first_pts=0" \
#   -c:v copy -c:a aac -b:a 192k \
#   -max_muxing_queue_size 1024 \
#   -avoid_negative_ts make_zero -movflags +faststart \
#   Raisanen-1987a-clean-v2.mp4

## NOTE: can't just copy the audio if there are discontinuities
