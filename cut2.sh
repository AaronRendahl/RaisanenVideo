#!/usr/bin/env zsh

# ==============================================================================
# CONFIGURATION & PARAMETERS
# ==============================================================================

VIDIN="Raisanen-1987a"

rm -f "$VIDIN"/*.png(N)

# Format: "IDX START_TIME END_TIME CROP_LEFT CROP_RIGHT CROP_TOP CROP_BOTTOM"
TIMES_LIST=(
  #"01 00:00:02.350 00:00:51.189 12 24 0 8"
  #"02 00:00:51.225 00:02:41.737 12 24 0 8"
  #"03 00:02:41.809 00:03:44.204 12 24 0 8"
  #"04 00:03:44.277 00:04:47.754 12 24 0 8"
  #"05 00:04:47.974 00:06:02.696 12 24 0 8"
  #"06 00:06:02.841 00:07:17.130 12 24 0 8"
  #"07 00:18:12.234 00:19:13.304 12 24 0 8"
  #"08 00:19:13.376 00:21:25.361 12 24 0 8"
  #"09 00:21:28.000 00:22:36.794 12 24 0 8"
  #"10 00:22:37.770 00:24:48.924 12 24 0 8"
  #"11 00:24:51.201 00:25:52.187 12 24 0 8"
  #"12 00:25:52.259 00:26:36.724 12 24 0 8"
  #"13 00:26:36.869 00:28:36.599 12 24 0 8"
  #"14 00:28:38.912 00:29:47.851 12 24 0 8"
  #"15 00:29:47.959 00:30:41.136 12 24 0 8"
  #"16 00:30:41.317 00:35:47.438 12 24 0 8"
  #"17 00:35:49.282 00:37:11.668 12 24 0 8"
  #"18 00:37:11.813 00:37:35.528 12 24 0 8"
  #"19 00:37:37.914 00:38:39.080 12 24 0 8"
  #"20 00:38:39.261 00:39:03.228 12 24 0 8"
  #"21 00:39:03.301 00:39:53.441 12 24 0 8"
  #"22 00:39:53.550 00:42:28.128 12 24 0 8"
  #"23 00:42:42.661 00:43:27.270 12 24 0 8"
  #"24 00:43:30.307 00:48:19.127 12 24 0 8"
  #"25 00:48:19.654 00:56:16.441 12 24 0 8"
  #"26 00:56:16.513 00:59:36.099 12 24 0 8"
  #"27 00:59:38.449 01:01:51.880 12 24 0 8"
  #"28 01:01:51.952 01:11:14.813 12 24 0 8"
  #"29 01:11:17.271 01:17:47.261 12 24 0 8"
  #"30 01:17:55.467 01:24:05.791 12 24 0 8"
  #"31 01:24:08.213 01:24:38.796 12 24 0 8"
  #"32 01:24:38.869 01:26:14.306 12 24 0 8"
  #"33 01:26:14.342 01:28:07.420 12 24 0 8"
  #"34 01:28:07.456 01:36:10.244 12 24 0 8"
  #"35 01:36:12.666 01:39:04.705 12 24 0 8"
  #"36 01:39:04.778 01:43:49.425 12 24 0 8"
  #"37 01:43:49.534 01:55:09.811 12 24 0 8"
  #"38 01:55:12.341 02:02:12.501 12 24 0 8"
)

INPUT_FILE="${VIDIN}.mov"

# Set and create output directory
OUTPUT_DIR="${VIDIN}"
mkdir -p "$OUTPUT_DIR"

# Encoding Settings
PARITY=0                  # 0 = Top Field First (TFF)
SAR="8/9"                 # NTSC 4:3 Aspect Ratio
AUDIO_BITRATE="192k"

# ==============================================================================
# TWO-STAGE PIPED ARCHIVAL PROCESSING PIPELINE (VHS NTSC -> UNIVERSAL MP4)
# ==============================================================================
# ARCHITECTURE: Stage 1 processes raw frames in memory and streams uncompressed
# YUV/PCM via a NUT RAM pipe (`pipe:1 | pipe:0`) directly into Stage 2.
# This prevents intermediate disk reads/writes while guaranteeing sync and compatibility.
#
# STAGE 1 (Demuxing & Frame Restructuring):
#   - -fflags +genpts+discardcorrupt : Fixes broken capture timestamps & drops bad packets.
#   - -ss / -to                      : Fast input seeking before decoding.
#   - yadif=mode=1:parity=0          : Deinterlaces 59.94 fields/sec -> 59.94 full FPS.
#   - crop=in_w-12-24:in_h-0-8:12:0  : Removes side overscan & bottom head-switching noise.
#   - setsar=8/9                     : Forces correct 4:3 NTSC display aspect ratio metadata.
#   - format=yuv420p                 : Downsamples color in RAM to minimize pipe memory bandwidth.
#   - -af "aresample=async=1"        : Prevents audio/video sync drift on dropped tape frames.
#
# STAGE 2 (Encoding & Container Packaging):
#   - setpts=PTS-STARTPTS            : Resets frame timestamps to t=0.0s for Finder thumbnails.
#   - -c:v libx264 -crf 22           : Software encode; optimal grain/noise handling for analog tape.
#   - -pix_fmt yuv420p -tag:v avc1   : Standard 8-bit YUV + FourCC tag for Apple/universal playability.
#   - -color_... smpte170m           : Sets Rec.601 NTSC color tags (prevents QuickTime washed-out look).
#   - -movflags +faststart           : Relocates moov atom header to front for instant web/Finder previews.
#   - -shortest                      : Instantly closes container when video track ends.
# ==============================================================================

# ==============================================================================
# PIPELINE EXECUTION LOOP
# ==============================================================================

for TIMES in "${TIMES_LIST[@]}"; do
  VALS=(${(s: :)TIMES})
  IDX=$VALS[1]
  START_TIME=$VALS[2]
  END_TIME=$VALS[3]
  CROP_LEFT_PX=$VALS[4]
  CROP_RIGHT_PX=$VALS[5]
  CROP_TOP_PX=$VALS[6]
  CROP_BOTTOM_PX=$VALS[7]

  OUTPUT_NAME="${OUTPUT_DIR}/${VIDIN}-${IDX}.mp4"
  PNG_BEFORE="${OUTPUT_DIR}/${VIDIN}-${IDX}-a0.png"
  PNG_AFTER_FIRST="${OUTPUT_DIR}/${VIDIN}-${IDX}-a1.png"
  PNG_AFTER_LAST="${OUTPUT_DIR}/${VIDIN}-${IDX}-a2.png"

  # Construct Crop Filter
  CROP_W="in_w-${CROP_LEFT_PX}-${CROP_RIGHT_PX}"
  CROP_H="in_h-${CROP_TOP_PX}-${CROP_BOTTOM_PX}"
  CROP_FILTER="crop=${CROP_W}:${CROP_H}:${CROP_LEFT_PX}:${CROP_TOP_PX}"

  VF_FILTERS="yadif=mode=1:parity=${PARITY},${CROP_FILTER},setsar=${SAR},format=yuv420p"

  echo "=========================================="
  echo "Processing Clip ${IDX}: $START_TIME to $END_TIME"
  echo "Output Target: $OUTPUT_NAME"
  echo "=========================================="

  # 1. Raw First-Frame PNG (Uncropped 720x480)
  ffmpeg -hide_banner -loglevel error -y \
    -ss "$START_TIME" -i "$INPUT_FILE" -vframes 1 \
    -vf "yadif=mode=1:parity=${PARITY}, scale=iw*sar:ih" \
    -pix_fmt rgb24 -update 1 "$PNG_BEFORE"

  # 2. Process the video using two-stage system, as described above
  ffmpeg -hide_banner -loglevel error -y \
    -fflags +genpts+discardcorrupt \
    -ss "$START_TIME" -to "$END_TIME" -i "$INPUT_FILE" \
    -vf "${VF_FILTERS}" \
    -af "aresample=async=1" \
    -c:v rawvideo \
    -c:a pcm_s16le \
    -f nut pipe:1 | \
  ffmpeg -hide_banner -loglevel error -y \
    -f nut -i pipe:0 \
    -vf "setpts=PTS-STARTPTS" \
    -c:v libx264 -crf 22 -preset fast -pix_fmt yuv420p \
    -tag:v avc1 -g 60 \
    -color_primaries smpte170m -color_trc smpte170m -colorspace smpte170m \
    -c:a aac -b:a "$AUDIO_BITRATE" \
    -movflags +faststart -shortest \
    "$OUTPUT_NAME"

  # alternatively, use hardware encoding:
  # -c:v h264_videotoolbox -q:v 55 -profile:v main -pix_fmt yuv420p \

  # 3a. Rendered File First-Frame Check
  ffmpeg -hide_banner -loglevel error -y \
    -i "$OUTPUT_NAME" -vframes 1 \
    -vf "scale=iw*sar:ih" -pix_fmt rgb24 -update 1 "$PNG_AFTER_FIRST"

  # 3b. Rendered File Last-Frame Check
  ffmpeg -hide_banner -loglevel error -y \
    -sseof -1 -i "$OUTPUT_NAME" \
    -vf "scale=iw*sar:ih" -pix_fmt rgb24 -update 1 "$PNG_AFTER_LAST"

  echo "Done Clip ${IDX}!"
  echo "Raw first frame:      $PNG_BEFORE"
  echo "Rendered first frame: $PNG_AFTER_FIRST"
  echo "Rendered last frame:  $PNG_AFTER_LAST"
  echo "Video exported:       $OUTPUT_NAME"
done

echo "=========================================="
echo "All active clips completed!"
echo "=========================================="


