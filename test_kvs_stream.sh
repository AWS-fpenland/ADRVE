#!/bin/bash

# Script to test if the KVS stream is working properly
# This will:
# 1. Check if the stream exists
# 2. Get the HLS streaming URL
# 3. Try to play the stream using ffplay (if available)

STREAM_NAME="adrve-video-stream"
REGION="us-west-2"

echo "Testing KVS stream: $STREAM_NAME in region $REGION"

# Check if the stream exists
echo "Checking if stream exists..."
aws kinesisvideo describe-stream --stream-name $STREAM_NAME --region $REGION

if [ $? -ne 0 ]; then
    echo "Error: Stream does not exist or you don't have permission to access it."
    exit 1
fi

# Get the HLS streaming endpoint
echo "Getting HLS streaming endpoint..."
HLS_ENDPOINT=$(aws kinesisvideo get-data-endpoint --stream-name $STREAM_NAME --api-name GET_HLS_STREAMING_SESSION_URL --region $REGION --query 'DataEndpoint' --output text)

if [ -z "$HLS_ENDPOINT" ]; then
    echo "Error: Failed to get HLS endpoint."
    exit 1
fi

echo "HLS endpoint: $HLS_ENDPOINT"

# Get the HLS streaming URL
echo "Getting HLS streaming URL..."
HLS_URL=$(aws kinesis-video-archived-media get-hls-streaming-session-url \
    --endpoint-url $HLS_ENDPOINT \
    --stream-name $STREAM_NAME \
    --playback-mode LIVE \
    --region $REGION \
    --query 'HLSStreamingSessionURL' \
    --output text)

if [ -z "$HLS_URL" ]; then
    echo "Error: Failed to get HLS streaming URL."
    exit 1
fi

echo "HLS streaming URL: $HLS_URL"

# Check if ffplay is available
if command -v ffplay &> /dev/null; then
    echo "ffplay is available. Attempting to play the stream..."
    echo "Press 'q' to quit."
    ffplay -fflags nobuffer -flags low_delay -framedrop "$HLS_URL"
else
    echo "ffplay is not available. You can manually test the stream with the URL above."
    echo "You can use VLC or any HLS compatible player to open this URL."
fi

echo "Test complete."
