#!/usr/bin/env zsh

VIDIN="Raisanen-8mm"

# Set to "" or "all" to run every clip.
# Set to a specific number (e.g., "07" or "02 05") to run only those clips.
RUN_ONLY="all"

CLIPS=(
  "01 00:00:00 00:12:35"
  "02 00:12:55 00:26:23"
  "03 00:26:27 00:39:16"
  "04 00:39:36 00:53:48"
  "05 00:53:53 01:02:07"
  "06 01:02:17 01:12:48"
  "07 01:13:15 01:29:24"
  "08 01:29:32 01:32:38"
)

for CLIP in "${CLIPS[@]}"; do
  read -r IDX START END <<< "$CLIP"

  # Check if RUN_ONLY is set to a specific clip index
  if [[ -n "$RUN_ONLY" && "$RUN_ONLY" != "all" ]]; then
    MATCH=false
    for TARGET in $RUN_ONLY; do
      if [[ "$IDX" == "$TARGET" ]]; then
        MATCH=true
        break
      fi
    done

    # Skip clip if it doesn't match RUN_ONLY
    if [[ "$MATCH" == false ]]; then
      continue
    fi
  fi

  RAW_OUT="${VIDIN}-${IDX}-raw.mp4"
  FINAL_OUT="${VIDIN}-${IDX}.mp4"

  echo "=========================================="
  echo "Processing Segment $IDX ($START to $END)"
  echo "=========================================="

  # Stage 1: Lossless Cut
  ffmpeg -y -ss "$START" -to "$END" -i "${VIDIN}.mpg" \
    -c copy -movflags +faststart \
    -y "$RAW_OUT"

  # Stage 2: Deinterlace, Crop Noise, Adjust Aspect Ratio, Fix Speed
  ffmpeg -y -fflags +genpts -i "$RAW_OUT" \
    -vf "yadif=mode=1:parity=0,crop=in_w:in_h-8:0:0,setsar=8/9,setpts=1.5*PTS" -r 24 \
    -c:v h264_videotoolbox -b:v 3500k -pix_fmt yuv420p \
    -an -movflags +faststart \
    -y "$FINAL_OUT"
done
