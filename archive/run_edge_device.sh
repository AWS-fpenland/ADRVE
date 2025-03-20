#!/bin/bash

# Script to run the ADRVE Edge Device with proper AWS credentials
# Usage: ./run_edge_device.sh [--profile PROFILE_NAME]

# Parse command line arguments
PROFILE="default"

while [[ $# -gt 0 ]]; do
  case $1 in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./run_edge_device.sh [--profile PROFILE_NAME]"
      exit 1
      ;;
  esac
done

echo "Using profile: $PROFILE"

# Set up GStreamer environment
KVS_PRODUCER_PATH="/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"
export GST_PLUGIN_PATH=$KVS_PRODUCER_PATH
export LD_LIBRARY_PATH=$KVS_PRODUCER_PATH:$LD_LIBRARY_PATH

echo "GST_PLUGIN_PATH set to $GST_PLUGIN_PATH"
echo "LD_LIBRARY_PATH includes $KVS_PRODUCER_PATH"

# Check if AWS credentials are already set in environment
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "AWS credentials not found in environment variables."
    echo "Please set AWS credentials before running this script:"
    echo "  export AWS_ACCESS_KEY_ID=your_access_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret_key"
    echo "  export AWS_SESSION_TOKEN=your_session_token  # if using temporary credentials"
    echo "  export AWS_DEFAULT_REGION=us-west-2"
    exit 1
fi

echo "Using AWS credentials from environment variables:"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:5}..."
echo "AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:0:5}..."
if [ ! -z "$AWS_SESSION_TOKEN" ]; then
    echo "AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN:0:5}..."
fi
echo "AWS_DEFAULT_REGION: ${AWS_DEFAULT_REGION:-us-west-2}"

# Set default region if not already set
if [ -z "$AWS_DEFAULT_REGION" ]; then
    export AWS_DEFAULT_REGION="us-west-2"
    echo "AWS_DEFAULT_REGION not set, using default: us-west-2"
fi

# Run the edge device script with the specified profile
echo "Running edge device script with profile: $PROFILE"
python edge-device-script.py --profile $PROFILE
