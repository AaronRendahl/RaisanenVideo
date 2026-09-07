#!/usr/bin/env zsh

# ==============================================================================
# INPUT ARGUMENTS & VALIDATION
# ==============================================================================

# Check if a tape name argument was provided on the command line
if [[ -z "$1" ]]; then
  echo "Error: No tape name provided!"
  echo "Usage: ./process_tape.sh <TAPE_NAME_WITHOUT_EXTENSION> [8mm]"
  echo "Example: ./process_tape.sh Raisanen-1987-Willy-40th"
  echo "Example: ./process_tape.sh Raisanen-1972-Lake-Trip 8mm"
  exit 1
fi

# Check if "8mm" was passed as the second command-line argument
IS_8MM=0
if [[ "$2" == "8mm" ]]; then
  IS_8MM=1
  echo ">>> 8mm Silent Mode Active (Speed: 16/24x, Audio: Disabled) <<<"
fi

# Set VIDIN and corresponding file paths from command-line arguments
VIDIN="$1"
INPUT_FILE="${VIDIN}.mkv"
TIMES_FILE="${VIDIN}.txt"

# Ensure input master video file exists
if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Error: Input file '$INPUT_FILE' not found!"
  exit 1
fi

# Ensure timestamp text file exists
if [[ ! -f "$TIMES_FILE" ]]; then
  echo "Error: Timestamp file '$TIMES_FILE' not found!"
  exit 1
fi

# Set and create output directory
OUTPUT_DIR="${VIDIN}"
mkdir -p "$OUTPUT_DIR"

# Clean up any leftover PNG checks from prior runs in the target directory
rm -f "${OUTPUT_DIR}"/*.png(N)

# ==============================================================================
# ENCODING CONFIGURATION
# ==============================================================================
PARITY=0                  # 0 = Top Field First (TFF)
SAR="8/9"                 # NTSC 4:3 Aspect Ratio
AUDIO_BITRATE="192k"

# ==============================================================================
# PIPELINE EXECUTION LOOP
# ==============================================================================

while IFS="|" read -r IDX START_TIME END_TIME CROP_LEFT_PX CROP_RIGHT_PX CROP_TOP_PX CROP_BOTTOM_PX RAW_LABEL; do

  # Strip any accidental hidden whitespace or carriage returns
  IDX="$(echo -n "$IDX" | xargs)"

  # Skip empty lines or commented lines starting with '#'
  if [[ -z "$IDX" || "$IDX" == \#* ]]; then
    continue
  fi

  # Sanitize label for filenames (replaces spaces with hyphens)
  LABEL="${RAW_LABEL// /-}"

  # Construct output paths (MP4 includes label; PNG verification thumbnails do not)
  OUTPUT_NAME="${OUTPUT_DIR}/${VIDIN}-${IDX}-${LABEL}.mp4"
  PNG_BEFORE="${OUTPUT_DIR}/${VIDIN}-${IDX}-a0.png"
  PNG_AFTER_FIRST="${OUTPUT_DIR}/${VIDIN}-${IDX}-a1.png"
  PNG_AFTER_LAST="${OUTPUT_DIR}/${VIDIN}-${IDX}-a2.png"

  # Construct Crop Filter
  CROP_W="in_w-${CROP_LEFT_PX}-${CROP_RIGHT_PX}"
  CROP_H="in_h-${CROP_TOP_PX}-${CROP_BOTTOM_PX}"
  CROP_FILTER="crop=${CROP_W}:${CROP_H}:${CROP_LEFT_PX}:${CROP_TOP_PX}"

  # Base Video Filters: Deinterlace -> Crop -> Aspect Ratio -> Color Format
  BASE_VF="yadif=mode=1:parity=${PARITY},${CROP_FILTER},setsar=${SAR},format=yuv420p"

  if [[ "$IS_8MM" -eq 1 ]]; then
    # 8mm Mode: Reset start PTS and slow video by 1.5x in Stage 1
    VF_STAGE1="${BASE_VF},setpts=(PTS-STARTPTS)*1.5"
    VF_STAGE2="null" # Bypass secondary PTS recalculation in Stage 2
    AUDIO_STAGE1="-an"
    AUDIO_STAGE2="-an"
  else
    # Standard VHS Mode
    VF_STAGE1="${BASE_VF}"
    VF_STAGE2="setpts=PTS-STARTPTS"
    AUDIO_STAGE1="-af aresample=async=1 -c:a pcm_s16le"
    AUDIO_STAGE2="-c:a aac -b:a $AUDIO_BITRATE"
  fi

  echo "=========================================="
  echo "Processing Clip ${IDX} (${RAW_LABEL}): $START_TIME to $END_TIME"
  echo "Output Target: $OUTPUT_NAME"
  echo "=========================================="

  # 1. Raw First-Frame PNG (Uncropped 720x480)
  ffmpeg -nostdin -hide_banner -loglevel error -y \
    -ss "$START_TIME" -i "$INPUT_FILE" -vframes 1 \
    -vf "yadif=mode=1:parity=${PARITY}, scale=iw*sar:ih" \
    -pix_fmt rgb24 -update 1 "$PNG_BEFORE"

  # 2. Process the video using the two-stage RAM pipe
  ffmpeg -nostdin -hide_banner -loglevel error -y \
    -fflags +genpts+discardcorrupt \
    -ss "$START_TIME" -to "$END_TIME" -i "$INPUT_FILE" \
    -vf "${VF_STAGE1}" \
    $=AUDIO_STAGE1 \
    -c:v rawvideo -pix_fmt yuv420p \
    -f nut pipe:1 | \
  ffmpeg -nostdin -hide_banner -loglevel error -y \
    -f nut -i pipe:0 \
    -vf "${VF_STAGE2}" \
    -c:v libx264 -crf 22 -preset fast -pix_fmt yuv420p \
    -tag:v avc1 -g 60 \
    -color_primaries smpte170m -color_trc smpte170m -colorspace smpte170m \
    $=AUDIO_STAGE2 \
    -movflags +faststart -shortest \
    "$OUTPUT_NAME"

  # 3a. Rendered File First-Frame Check
  ffmpeg -nostdin -hide_banner -loglevel error -y \
    -i "$OUTPUT_NAME" -vframes 1 \
    -vf "scale=iw*sar:ih" -pix_fmt rgb24 -update 1 "$PNG_AFTER_FIRST"

  # 3b. Rendered File Last-Frame Check
  ffmpeg -nostdin -hide_banner -loglevel error -y \
    -sseof -1 -i "$OUTPUT_NAME" \
    -vf "scale=iw*sar:ih" -pix_fmt rgb24 -update 1 "$PNG_AFTER_LAST"

  echo "Done Clip ${IDX}!"
  echo "Video exported: $OUTPUT_NAME"

done < "$TIMES_FILE"

echo "=========================================="
echo "All active clips completed!"
echo "=========================================="
