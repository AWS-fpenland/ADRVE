#!/bin/bash

# KVS environment variable test
# This script tests using environment variables for KVS configuration

# Configuration
PROFILE="org-master"
KVS_DIR="/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"
STREAM_NAME="adrve-video-stream"
AWS_REGION="us-west-2"

# Login to AWS SSO
aws sso login --profile $PROFILE

# Get AWS credentials using Python
cat > get_creds.py << EOF
import boto3
import json
import os

session = boto3.Session(profile_name='$PROFILE')
credentials = session.get_credentials()
cred_data = {
    "accessKeyId": credentials.access_key,
    "secretAccessKey": credentials.secret_key
}
if credentials.token:
    cred_data["sessionToken"] = credentials.token

print(json.dumps(cred_data))
EOF

# Run the Python script to get credentials
CREDS_JSON=$(python3 get_creds.py)
rm get_creds.py

# Extract credentials from JSON
ACCESS_KEY=$(echo $CREDS_JSON | python3 -c "import sys, json; print(json.load(sys.stdin)['accessKeyId'])")
SECRET_KEY=$(echo $CREDS_JSON | python3 -c "import sys, json; print(json.load(sys.stdin)['secretAccessKey'])")
SESSION_TOKEN=$(echo $CREDS_JSON | python3 -c "import sys, json; print(json.load(sys.stdin).get('sessionToken', ''))")

# Create .kvs directory in KVS build directory
mkdir -p "$KVS_DIR/../.kvs"

# Create credential file
cat > "$KVS_DIR/../.kvs/credential" << EOF
{
  "accessKeyId": "$ACCESS_KEY",
  "secretAccessKey": "$SECRET_KEY"
EOF

if [ ! -z "$SESSION_TOKEN" ]; then
    echo "  ,\"sessionToken\": \"$SESSION_TOKEN\"" >> "$KVS_DIR/../.kvs/credential"
fi

echo "}" >> "$KVS_DIR/../.kvs/credential"

echo "Credential file created at $KVS_DIR/../.kvs/credential"

# Set environment variables
export AWS_ACCESS_KEY_ID="$ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$SECRET_KEY"
if [ ! -z "$SESSION_TOKEN" ]; then
    export AWS_SESSION_TOKEN="$SESSION_TOKEN"
fi

# Set KVS environment variables
export KVS_STREAM_NAME="$STREAM_NAME"
export KVS_AWS_REGION="$AWS_REGION"
export KVS_VIDEO_WIDTH="640"
export KVS_VIDEO_HEIGHT="480"
export KVS_VIDEO_FPS="15"
export KVS_RETENTION_PERIOD="2"

# Run KVS producer with no parameters
cd "$KVS_DIR"
echo "Running KVS producer with environment variables..."
./kvs_gstreamer_sample
