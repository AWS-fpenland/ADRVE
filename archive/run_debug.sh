#!/bin/bash

# Script to run the debug version of the ADRVE Edge Device with a video file input
# Usage: ./run_debug.sh --video-file FILE.mkv [--profile PROFILE_NAME] [--no-display]

# Default values
PROFILE="org-master"
NO_DISPLAY=""
VIDEO_FILE=""

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
    --video-file)
      VIDEO_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./run_debug.sh --video-file FILE.mkv [--profile PROFILE_NAME] [--no-display]"
      exit 1
      ;;
  esac
done

# Check if video file is provided
if [ -z "$VIDEO_FILE" ]; then
  echo "Error: Video file is required"
  echo "Usage: ./run_debug.sh --video-file FILE.mkv [--profile PROFILE_NAME] [--no-display]"
  exit 1
fi

# Check if video file exists
if [ ! -f "$VIDEO_FILE" ]; then
  echo "Error: Video file '$VIDEO_FILE' not found"
  exit 1
fi

echo "Using profile: $PROFILE"
echo "Video file: $VIDEO_FILE"
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

# Start MQTT subscriber in background
echo "Starting MQTT subscriber in background..."
python mqtt_subscriber.py > mqtt_logs.txt 2>&1 &
MQTT_PID=$!
echo "MQTT subscriber started with PID: $MQTT_PID"

# Run the debug edge device script with video file
echo "Running debug edge device script with video file input..."
python edge-device-video-file-debug.py --profile $PROFILE $NO_DISPLAY --video-file "$VIDEO_FILE"

# Kill the MQTT subscriber when done
echo "Stopping MQTT subscriber..."
kill $MQTT_PID
echo "Done."
