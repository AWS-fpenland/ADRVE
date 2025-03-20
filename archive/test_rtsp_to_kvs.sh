#!/bin/bash

# Test script to stream RTSP to KVS
# Usage: ./test_rtsp_to_kvs.sh [profile_name] [rtsp_url]

# Default profile if not provided
PROFILE=${1:-"org-master"}
RTSP_URL=${2:-"rtsp://10.31.50.195:8554/test"}
STREAM_NAME="adrve-video-stream"
KVS_PRODUCER_PATH="/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"

echo "Setting up AWS credentials using profile: $PROFILE"

# Check if AWS SSO session is active
aws sts get-caller-identity --profile $PROFILE &> /dev/null
if [ $? -ne 0 ]; then
    echo "AWS SSO session not active or expired. Logging in..."
    aws sso login --profile $PROFILE
    
    # Check if login was successful
    if [ $? -ne 0 ]; then
        echo "Failed to log in with AWS SSO. Exiting."
        exit 1
    fi
    echo "AWS SSO login successful."
else
    echo "AWS SSO session is active."
fi

# Create a temporary file to store AWS CLI output
TEMP_CRED_FILE=$(mktemp)
echo "Using temporary file: $TEMP_CRED_FILE"

# Use AWS CLI with debug output to capture credentials
echo "Capturing AWS credentials..."
AWS_DEBUG=1 aws s3 ls --profile $PROFILE > $TEMP_CRED_FILE 2>&1

# Display the first few lines of the debug output (for troubleshooting)
echo "Debug output preview:"
head -20 $TEMP_CRED_FILE

# Extract credentials from the debug output
ACCESS_KEY=$(grep -o "aws_access_key_id = [A-Z0-9]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)
SECRET_KEY=$(grep -o "aws_secret_access_key = [A-Za-z0-9/+]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)
SESSION_TOKEN=$(grep -o "aws_session_token = [A-Za-z0-9/+=]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)

# Clean up
rm $TEMP_CRED_FILE

# Verify we have credentials
if [ -z "$ACCESS_KEY" ] || [ -z "$SECRET_KEY" ]; then
    echo "Failed to obtain AWS credentials. Exiting."
    exit 1
fi

echo "Successfully obtained AWS credentials:"
echo "Access Key ID: ${ACCESS_KEY:0:5}..."
echo "Secret Access Key: ${SECRET_KEY:0:5}..."
if [ ! -z "$SESSION_TOKEN" ]; then
    echo "Session Token: ${SESSION_TOKEN:0:5}..."
fi

# Create credential file for KVS
mkdir -p $KVS_PRODUCER_PATH/.kvs
cat > $KVS_PRODUCER_PATH/.kvs/credential << EOF
{
  "accessKeyId": "$ACCESS_KEY",
  "secretAccessKey": "$SECRET_KEY"
EOF

# Add session token if it exists
if [ ! -z "$SESSION_TOKEN" ]; then
    echo ',' >> $KVS_PRODUCER_PATH/.kvs/credential
    echo "  \"sessionToken\": \"$SESSION_TOKEN\"" >> $KVS_PRODUCER_PATH/.kvs/credential
fi

# Close the JSON
echo "}" >> $KVS_PRODUCER_PATH/.kvs/credential

# Export credentials for environment
export AWS_ACCESS_KEY_ID=$ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$SECRET_KEY
if [ ! -z "$SESSION_TOKEN" ]; then
    export AWS_SESSION_TOKEN=$SESSION_TOKEN
fi
export AWS_DEFAULT_REGION="us-west-2"

# Set up GStreamer environment
export GST_PLUGIN_PATH=$KVS_PRODUCER_PATH
export LD_LIBRARY_PATH=$KVS_PRODUCER_PATH:$LD_LIBRARY_PATH

echo "AWS credentials set up successfully"
echo "Credential file created at $KVS_PRODUCER_PATH/.kvs/credential"
echo "GST_PLUGIN_PATH set to $GST_PLUGIN_PATH"
echo "LD_LIBRARY_PATH includes $KVS_PRODUCER_PATH"

# Skip RTSP stream testing since ffprobe is not installed
echo "Skipping RTSP stream testing (ffprobe not installed)"

# Create the GStreamer pipeline command
echo "Starting GStreamer pipeline to stream RTSP to KVS..."
echo "RTSP URL: $RTSP_URL"
echo "KVS Stream: $STREAM_NAME"

# Method 1: Using gst-launch-1.0 with kvssink
echo "Running GStreamer pipeline with kvssink..."
gst-launch-1.0 -v rtspsrc location="$RTSP_URL" short-header=TRUE ! rtph264depay ! h264parse ! kvssink stream-name="$STREAM_NAME" storage-size=128

# If Method 1 fails, try Method 2
if [ $? -ne 0 ]; then
    echo "Method 1 failed. Trying Method 2: Using the KVS GStreamer sample..."
    cd $KVS_PRODUCER_PATH
    echo "Running from directory: $(pwd)"
    echo "Using command: ./kvs_gstreamer_sample $STREAM_NAME -rtsp \"$RTSP_URL\" -w 1280 -h 720 -f 15"
    ./kvs_gstreamer_sample $STREAM_NAME -rtsp "$RTSP_URL" -w 1280 -h 720 -f 15
fi
