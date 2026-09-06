#!/usr/bin/env zsh

# ==============================================================================
# CONFIGURATION & PARAMETERS
# ==============================================================================

VIDIN="Raisanen-1987a"

# Format: "IDX START_TIME END_TIME CROP_LEFT CROP_RIGHT CROP_TOP CROP_BOTTOM"
#TIMES="01 00:00:02.302 00:00:51.151 12 24  0  8"
#TIMES="02 00:00:51.184 00:02:41.561 12 24  0  8"
#TIMES="03 00:02:41.728 00:03:44.024 12 24  0  8"
#TIMES="04 00:03:44.157 00:04:47.754 12 24  0  8"
#TIMES="05 00:04:47.854 00:06:02.495 12 24  0  8"
#TIMES="06 00:06:02.662 00:07:17.003 12 24  0  8"
#TIMES="07 00:18:45.358 00:19:05.444 12 24  0  8"
TIMES="08 00:19:05.611 00:19:30.444 12 24  0  8"


# Set to true for 1-pass (Faster, no temp files)
# Set to false for 2-stage (Keeps intermediate raw cut for testing)
# 2-stage is also less likely to have a black preview, so default to that
SINGLE_PASS=false

VALS=(${(s: :)TIMES})
IDX=$VALS[1]
START_TIME=$VALS[2]
END_TIME=$VALS[3]
CROP_LEFT_PX=$VALS[4]
CROP_RIGHT_PX=$VALS[5]
CROP_TOP_PX=$VALS[6]
CROP_BOTTOM_PX=$VALS[7]

INPUT_FILE="${VIDIN}.mpg"
OUTPUT_NAME="${VIDIN}-${IDX}.mp4"
TEMP_RAW="${VIDIN}-${IDX}-raw.mp4"

ffmpeg -y -ss $START_TIME -i $INPUT_FILE -vframes 1 -vf "yadif=mode=1" "${VIDIN}-${IDX}.png"

# Speed Adjustment
SPEED_FACTOR=1.0          # 1.5 = 1.5x slow-down for silent 8mm; 1.0 = Native Speed (VHS with Audio)

# Video Adjustments
PARITY=0                  # 0 = Top Field First (TFF), 1 = Bottom Field First (BFF)
SAR="8/9"                 # Sample Aspect Ratio for 4:3 NTSC DVD/MPEG-2
VIDEO_BITRATE="3500k"     # Target bit rate for H.264 export

# Audio Adjustments (Used only when SPEED_FACTOR=1.0)
AUDIO_BITRATE="192k"      # Target AAC audio bit rate
# ==============================================================================

# Construct Crop Filter (out_w : out_h : x : y)
CROP_W="in_w-${CROP_LEFT_PX}-${CROP_RIGHT_PX}"
CROP_H="in_h-${CROP_TOP_PX}-${CROP_BOTTOM_PX}"
CROP_X="${CROP_LEFT_PX}"
CROP_Y="${CROP_TOP_PX}"

CROP_FILTER="crop=${CROP_W}:${CROP_H}:${CROP_X}:${CROP_Y}"

# Construct Video Filters and Audio Mode
if [[ "$SPEED_FACTOR" != "1.0" && "$SPEED_FACTOR" != "1" ]]; then
  VF_FILTERS="yadif=mode=1:parity=${PARITY},${CROP_FILTER},setsar=${SAR},setpts=${SPEED_FACTOR}*PTS"
  IS_SILENT=true
else
  VF_FILTERS="yadif=mode=1:parity=${PARITY},${CROP_FILTER},setsar=${SAR}"
  IS_SILENT=false
fi

echo "=========================================="
echo "Processing File: $INPUT_FILE"
echo "Cut Interval:    $START_TIME to $END_TIME"
echo "Speed Factor:    ${SPEED_FACTOR}x"
echo "Crop Settings:   L:${CROP_LEFT_PX} R:${CROP_RIGHT_PX} T:${CROP_TOP_PX} B:${CROP_BOTTOM_PX}"
echo "Audio Output:    $( [[ "$IS_SILENT" == true ]] && echo "Disabled (-an)" || echo "AAC ${AUDIO_BITRATE}" )"
echo "Output:          $OUTPUT_NAME"
echo "=========================================="

if [[ "$SINGLE_PASS" == true ]]; then

  if [[ "$IS_SILENT" == true ]]; then
    ffmpeg -y -fflags +genpts+discardcorrupt -avoid_negative_ts make_zero \
      -ss "$START_TIME" -to "$END_TIME" -i "$INPUT_FILE" \
      -vf "$VF_FILTERS" -an \
      -c:v h264_videotoolbox -b:v "$VIDEO_BITRATE" -profile:v main -pix_fmt yuv420p \
      -tag:v avc1 -g 30 -force_key_frames "expr:gte(t,n_forced*0.5)" \
      -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
      -movflags +faststart \
      "$OUTPUT_NAME"
  else
    ffmpeg -y -fflags +genpts+discardcorrupt -avoid_negative_ts make_zero \
      -ss "$START_TIME" -to "$END_TIME" -i "$INPUT_FILE" \
      -vf "$VF_FILTERS" \
      -af "aresample=async=1:first_pts=0" \
      -c:v h264_videotoolbox -b:v "$VIDEO_BITRATE" -profile:v main -pix_fmt yuv420p \
      -tag:v avc1 -g 30 -force_key_frames "expr:gte(t,n_forced*0.5)" \
      -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
      -c:a aac -b:a "$AUDIO_BITRATE" \
      -movflags +faststart \
      "$OUTPUT_NAME"
  fi

else

  if [[ "$IS_SILENT" == true ]]; then
    # Stage 1: Extract rough raw slice (fast copy)
    ffmpeg -y -ss "$START_TIME" -to "$END_TIME" -i "$INPUT_FILE" \
      -c:v copy -an \
      -avoid_negative_ts make_zero -movflags +faststart \
      "$TEMP_RAW"

    # Stage 2: Decode from source using precise timestamps, encode clean H.264
    ffmpeg -y -fflags +genpts -ss "$START_TIME" -to "$END_TIME" -i "$INPUT_FILE" \
      -vf "$VF_FILTERS" -an \
      -c:v h264_videotoolbox -b:v "$VIDEO_BITRATE" -profile:v main -pix_fmt yuv420p \
      -tag:v avc1 -g 30 \
      -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
      -avoid_negative_ts make_zero -movflags +faststart \
      "$OUTPUT_NAME"
  else
    # Stage 1: Fast Raw Cut + AAC Audio Sync Copy
    ffmpeg -y -ss "$START_TIME" -to "$END_TIME" -i "$INPUT_FILE" \
      -c:v copy -c:a aac -b:a "$AUDIO_BITRATE" \
      -af "aresample=async=1:first_pts=0" \
      -avoid_negative_ts make_zero -movflags +faststart \
      "$TEMP_RAW"

    # Stage 2: Decode from source using precise timestamps + match AAC audio
    ffmpeg -y -fflags +genpts -i "$TEMP_RAW" -ss 00:00:00.000 \
      -vf "$VF_FILTERS" \
      -af "aresample=async=1:first_pts=0" \
      -c:v h264_videotoolbox -b:v "$VIDEO_BITRATE" -profile:v main -pix_fmt yuv420p \
      -tag:v avc1 -g 30 \
      -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
      -c:a aac -b:a "$AUDIO_BITRATE" \
      -avoid_negative_ts make_zero -movflags +faststart \
      "$OUTPUT_NAME"
  fi

fi

# ==============================================================================
# CLEANUP TEMPORARY FILES
# ==============================================================================
if [[ -f "$TEMP_RAW" ]]; then
  echo "Cleaning up temporary raw file: $TEMP_RAW"
  rm -f "$TEMP_RAW"
fi

echo "=========================================="
echo "Done! Final video saved to $OUTPUT_NAME"
echo "=========================================="
