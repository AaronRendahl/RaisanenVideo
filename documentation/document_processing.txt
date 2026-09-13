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
#   - crop=...                       : Removes side overscan & bottom head-switching noise.
#   - setsar=8/9                     : Forces correct 4:3 NTSC display aspect ratio metadata.
#   - format=yuv420p                 : Downsamples color in RAM to minimize pipe memory bandwidth.
#   - setpts=(PTS-STARTPTS)*1.5      : Slows 16fps silent 8mm film to 24fps when enabled.
#   - -af "aresample=async=1"        : Prevents audio/video sync drift on dropped tape frames.
#
# STAGE 2 (Encoding & Container Packaging):
#   - setpts=PTS-STARTPTS            : Resets frame timestamps to t=0.0s for standard video clips.
#   - -c:v libx264 -crf 22           : Software encode; optimal grain/noise handling for analog tape.
#   - -pix_fmt yuv420p -tag:v avc1   : Standard 8-bit YUV + FourCC tag for Apple/universal playability.
#   - -color_... smpte170m           : Sets Rec.601 NTSC color tags (prevents QuickTime washed-out look).
#   - -movflags +faststart           : Relocates moov atom header to front for instant web/Finder previews.
#   - -shortest                      : Instantly closes container when video track ends.
# ==============================================================================
