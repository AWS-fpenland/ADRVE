#!/bin/bash

# Test script to stream RTMP to KVS using environment variables for credentials
# Usage: ./test_rtmp_env_creds.sh [rtmp_url]

# Default values
RTMP_URL=${1:-"rtmp://10.31.50.195:1935/live/test"}
STREAM_NAME="adrve-video-stream"
KVS_PRODUCER_PATH="/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"

# Check if AWS credentials are set in environment
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "AWS credentials not found in environment variables."
    echo "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script."
    echo "Example:"
    echo "  export AWS_ACCESS_KEY_ID=your_access_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret_key"
    echo "  export AWS_SESSION_TOKEN=your_session_token  # if using temporary credentials"
    exit 1
fi

echo "Using AWS credentials from environment variables:"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:5}..."
echo "AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:0:5}..."
if [ ! -z "$AWS_SESSION_TOKEN" ]; then
    echo "AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN:0:5}..."
fi

# Set default region if not already set
if [ -z "$AWS_DEFAULT_REGION" ]; then
    export AWS_DEFAULT_REGION="us-west-2"
    echo "AWS_DEFAULT_REGION not set, using default: us-west-2"
else
    echo "Using AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"
fi

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

# Set up GStreamer environment
export GST_PLUGIN_PATH=$KVS_PRODUCER_PATH
export LD_LIBRARY_PATH=$KVS_PRODUCER_PATH:$LD_LIBRARY_PATH

echo "Credential file created at $KVS_PRODUCER_PATH/.kvs/credential"
echo "GST_PLUGIN_PATH set to $GST_PLUGIN_PATH"
echo "LD_LIBRARY_PATH includes $KVS_PRODUCER_PATH"

# Skip RTMP stream testing since ffprobe is not installed
echo "Skipping RTMP stream testing (ffprobe not installed)"

# Create the GStreamer pipeline command
echo "Starting KVS GStreamer sample to stream RTMP to KVS..."
echo "RTMP URL: $RTMP_URL"
echo "KVS Stream: $STREAM_NAME"

# Use the KVS GStreamer sample
cd $KVS_PRODUCER_PATH
echo "Running from directory: $(pwd)"
echo "Using command: ./kvs_gstreamer_sample $STREAM_NAME -r \"$RTMP_URL\" -w 1280 -h 720 -f 15"
./kvs_gstreamer_sample $STREAM_NAME -r "$RTMP_URL" -w 1280 -h 720 -f 15
