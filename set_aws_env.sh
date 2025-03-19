#!/bin/bash

# Script to set AWS environment variables for testing
# Usage: source ./set_aws_env.sh

# Replace these with your actual AWS credentials
export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY"
export AWS_SESSION_TOKEN="YOUR_SESSION_TOKEN"  # Remove if not using temporary credentials
export AWS_DEFAULT_REGION="us-west-2"

# Set up GStreamer environment
KVS_PRODUCER_PATH="/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"
export GST_PLUGIN_PATH=$KVS_PRODUCER_PATH
export LD_LIBRARY_PATH=$KVS_PRODUCER_PATH:$LD_LIBRARY_PATH

echo "AWS environment variables set:"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:5}..."
echo "AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:0:5}..."
if [ ! -z "$AWS_SESSION_TOKEN" ]; then
    echo "AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN:0:5}..."
fi
echo "AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"
echo "GST_PLUGIN_PATH: $GST_PLUGIN_PATH"
echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"

echo "You can now run the edge device script:"
echo "./run_edge_device.sh --profile default"
