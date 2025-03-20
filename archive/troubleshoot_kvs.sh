#!/bin/bash

# Script to troubleshoot KVS streaming issues
# Usage: ./troubleshoot_kvs.sh [rtsp_url]

# Default values
RTSP_URL=${1:-"rtsp://10.31.50.195:554/live"}
STREAM_NAME="adrve-video-stream"
KVS_PRODUCER_PATH="/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"

# Check if AWS credentials are set in environment
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "AWS credentials not found in environment variables."
    echo "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script."
    exit 1
fi

echo "Using AWS credentials from environment variables"
echo "RTSP URL: $RTSP_URL"
echo "KVS Stream: $STREAM_NAME"

# Set up GStreamer environment
export GST_PLUGIN_PATH=$KVS_PRODUCER_PATH
export LD_LIBRARY_PATH=$KVS_PRODUCER_PATH:$LD_LIBRARY_PATH
export GST_DEBUG=3

# Create credential file for KVS
mkdir -p $KVS_PRODUCER_PATH/.kvs
cat > $KVS_PRODUCER_PATH/.kvs/credential << EOF
{
  "accessKeyId": "$AWS_ACCESS_KEY_ID",
  "secretAccessKey": "$AWS_SECRET_ACCESS_KEY"
EOF

# Add session token if it exists
if [ ! -z "$AWS_SESSION_TOKEN" ]; then
    echo ',' >> $KVS_PRODUCER_PATH/.kvs/credential
    echo "  \"sessionToken\": \"$AWS_SESSION_TOKEN\"" >> $KVS_PRODUCER_PATH/.kvs/credential
fi

# Close the JSON
echo "}" >> $KVS_PRODUCER_PATH/.kvs/credential

echo "Credential file created at $KVS_PRODUCER_PATH/.kvs/credential"

# Step 1: Test RTSP stream with ffprobe (if available)
echo "Step 1: Testing RTSP stream..."
if command -v ffprobe &> /dev/null; then
    echo "Using ffprobe to analyze RTSP stream..."
    ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,avg_frame_rate -of default=noprint_wrappers=1 $RTSP_URL
else
    echo "ffprobe not found, skipping RTSP analysis"
    echo "Consider installing ffmpeg: sudo apt install ffmpeg"
fi

# Step 2: Test RTSP stream with GStreamer
echo "Step 2: Testing RTSP stream with GStreamer..."
echo "Running for 10 seconds to check frame rate and stability..."
timeout 10s gst-launch-1.0 -v rtspsrc location="$RTSP_URL" short-header=TRUE ! \
    rtph264depay ! h264parse ! fakesink sync=false

# Step 3: Test with modified GStreamer pipeline (more robust)
echo "Step 3: Testing with modified GStreamer pipeline..."
echo "Running for 10 seconds with more robust settings..."
timeout 10s gst-launch-1.0 -v rtspsrc location="$RTSP_URL" latency=0 buffer-mode=auto ! \
    rtph264depay ! h264parse ! fakesink sync=false

# Step 4: Test with KVS (with modified parameters)
echo "Step 4: Testing with KVS (with modified parameters)..."
echo "Running for 30 seconds with optimized KVS settings..."
timeout 30s gst-launch-1.0 -v rtspsrc location="$RTSP_URL" latency=0 buffer-mode=auto ! \
    rtph264depay ! h264parse ! \
    video/x-h264,stream-format=avc,alignment=au ! \
    kvssink stream-name="$STREAM_NAME" storage-size=512 max-latency=0 fragment-duration=2000 key-frame-fragmentation=true

echo "Troubleshooting complete. Check the output for errors and warnings."
echo "If you're still experiencing issues, try the following:"
echo "1. Increase the storage-size parameter (e.g., 512 or 1024)"
echo "2. Decrease the fragment-duration parameter (e.g., 1000 or 2000)"
echo "3. Check your network connection to the RTSP source"
echo "4. Verify that the RTSP source is providing a stable H.264 stream"
