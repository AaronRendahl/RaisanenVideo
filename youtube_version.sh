#!/zsh
# make_yt_copies.sh - Batch convert existing 8mm MP4s to 59.94 FPS for YouTube

LOCAL_DIR="./Raisanen-8mm"  # Path to your processed local files
YOUTUBE_DIR="./Raisanen-8mm-YouTube"

# 1. Ensure the destination folder exists before ffmpeg attempts to save files
mkdir -p "$YOUTUBE_DIR"

for file in "$LOCAL_DIR"/*.mp4; do
  # Skip files that are already YouTube variants
  if [[ "$file" == *"_YouTube.mp4"* ]]; then
    continue
  fi

  # 2. Extract base filename (e.g. "Clip01") without directory or extension
  output_yt="$YOUTUBE_DIR/${file:t:r}_YouTube.mp4"

  echo "Creating YouTube variant for: ${file:t}"

  ffmpeg -y -i "$file" \
    -vf "fps=59.94" \
    -c:v libx264 \
    -crf 18 \
    -preset fast \
    -movflags +faststart \
    "$output_yt"

  echo "Done: ${output_yt:t}"
  echo "----------------------------------------"
done
