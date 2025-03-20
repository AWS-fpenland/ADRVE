#!/bin/bash

# Optimized script for streaming RTSP to KVS with improved performance
# Usage: ./optimized_rtsp_to_kvs.sh [rtsp_url]

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
export GST_DEBUG=2  # Reduced debug level for better performance

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

# Set default region if not already set
if [ -z "$AWS_DEFAULT_REGION" ]; then
    export AWS_DEFAULT_REGION="us-west-2"
    echo "AWS_DEFAULT_REGION not set, using default: us-west-2"
else
    echo "Using AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"
fi

# Run the optimized GStreamer pipeline
echo "Starting optimized GStreamer pipeline to stream RTSP to KVS..."
echo "Press Ctrl+C to stop streaming"

# Optimized pipeline with improved parameters:
# - latency=0: Minimize latency
# - buffer-mode=auto: Let GStreamer handle buffering
# - storage-size=512: Larger buffer for smoother streaming
# - max-latency=0: Minimize latency in KVS
# - fragment-duration=2000: Shorter fragments (2 seconds)
# - key-frame-fragmentation=true: Fragment on key frames
# - frame-rate=30: Explicitly set frame rate
# - nal-adaptation-flags=0x0: No NAL adaptation
gst-launch-1.0 -v \
    rtspsrc location="$RTSP_URL" latency=0 buffer-mode=auto ! \
    rtph264depay ! h264parse ! \
    video/x-h264,stream-format=avc,alignment=au ! \
    kvssink stream-name="$STREAM_NAME" \
        storage-size=512 \
        max-latency=0 \
        fragment-duration=2000 \
        key-frame-fragmentation=true \
        frame-rate=30 \
        nal-adaptation-flags=0x0
