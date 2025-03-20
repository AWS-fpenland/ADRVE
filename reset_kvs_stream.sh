#!/bin/bash

# Script to reset the KVS stream to fix timestamp issues
# Usage: ./reset_kvs_stream.sh [stream_name]

# Default values
STREAM_NAME=${1:-"adrve-video-stream"}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    echo "Run: pip install awscli"
    exit 1
fi

# Check if AWS credentials are set
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "AWS credentials not found in environment variables."
    echo "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script."
    exit 1
fi

# Set default region if not already set
if [ -z "$AWS_DEFAULT_REGION" ]; then
    export AWS_DEFAULT_REGION="us-west-2"
    echo "AWS_DEFAULT_REGION not set, using default: us-west-2"
else
    echo "Using AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"
fi

echo "Resetting KVS stream: $STREAM_NAME"

# Check if the stream exists
echo "Checking if stream exists..."
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

echo "KVS stream reset complete. You can now run your streaming application."
