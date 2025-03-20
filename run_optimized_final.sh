#!/bin/bash

# Script to run the optimized ADRVE Edge Device (final version)
# Usage: ./run_optimized_final.sh [--profile PROFILE_NAME] [--no-display] [--rtsp-url URL]

# Default values
PROFILE="default"
NO_DISPLAY=""
RTSP_URL="rtsp://10.31.50.195:554/live"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --no-display)
      NO_DISPLAY="--no-display"
      shift
      ;;
    --rtsp-url)
      RTSP_URL="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./run_optimized_final.sh [--profile PROFILE_NAME] [--no-display] [--rtsp-url URL]"
      exit 1
      ;;
  esac
done

echo "Using profile: $PROFILE"
echo "RTSP URL: $RTSP_URL"
echo "Local Display: $([ -z "$NO_DISPLAY" ] && echo "Enabled" || echo "Disabled")"

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

# Run the optimized edge device script
echo "Running optimized edge device script (final version)..."
python edge-device-optimized-final.py --profile $PROFILE $NO_DISPLAY --rtsp-url "$RTSP_URL"
