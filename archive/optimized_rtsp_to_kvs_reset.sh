#!/bin/bash

# Optimized script for streaming RTSP to KVS with complete reset
# Usage: ./optimized_rtsp_to_kvs_reset.sh [rtsp_url]

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

# First, reset the KVS stream
echo "Resetting KVS stream..."
if command -v aws &> /dev/null; then
    # Check if the stream exists
    if aws kinesisvideo describe-stream --stream-name "$STREAM_NAME" &> /dev/null; then
        echo "Stream exists. Deleting stream..."
        aws kinesisvideo delete-stream --stream-name "$STREAM_NAME"
        
        # Wait for the stream to be deleted
        echo "Waiting for stream to be deleted..."
        sleep 5
        
        # Check if deletion was successful
        while aws kinesisvideo describe-stream --stream-name "$STREAM_NAME" &> /dev/null; do
            echo "Stream still exists. Waiting..."
            sleep 5
        done
        
        echo "Stream deleted successfully."
    else
        echo "Stream does not exist."
    fi

    # Create a new stream
    echo "Creating new stream: $STREAM_NAME"
    aws kinesisvideo create-stream \
        --stream-name "$STREAM_NAME" \
        --data-retention-in-hours 24 \
        --media-type "video/h264"

    # Check if creation was successful
    if aws kinesisvideo describe-stream --stream-name "$STREAM_NAME" &> /dev/null; then
        echo "Stream created successfully."
    else
        echo "Failed to create stream."
        exit 1
    fi
else
    echo "AWS CLI not found. Skipping stream reset."
    echo "Install AWS CLI with: pip install awscli"
fi

# Run the optimized GStreamer pipeline with extreme timestamp fix
echo "Starting optimized GStreamer pipeline with extreme timestamp fix..."
echo "Press Ctrl+C to stop streaming"

# Pipeline with extreme timestamp fix:
# 1. Use a very long fragment duration (10 seconds)
# 2. Disable absolute fragment times
# 3. Use a large storage size (1024MB)
# 4. Disable timecode scaling
gst-launch-1.0 -v \
    rtspsrc location="$RTSP_URL" latency=0 buffer-mode=auto ! \
    rtph264depay ! \
    h264parse ! \
    video/x-h264,stream-format=avc,alignment=au ! \
    kvssink stream-name="$STREAM_NAME" \
        storage-size=1024 \
        max-latency=0 \
        fragment-duration=10000 \
        key-frame-fragmentation=true \
        absolute-fragment-times=false \
        timecode-scale=1
