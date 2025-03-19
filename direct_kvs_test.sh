#!/bin/bash

# Direct KVS test with minimal parameters
# This script tests the KVS producer with the most basic command line

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

# Run KVS producer with minimal parameters
cd "$KVS_DIR"
echo "Running KVS producer with minimal parameters..."

# Try different parameter formats
echo "Method 1: Using single parameter string"
./kvs_gstreamer_sample STREAM_NAME=$STREAM_NAME

echo "Method 2: Using quoted parameter"
./kvs_gstreamer_sample "STREAM_NAME=$STREAM_NAME"

echo "Method 3: Using equals sign"
./kvs_gstreamer_sample STREAM_NAME="$STREAM_NAME"

echo "Method 4: Using space separator"
./kvs_gstreamer_sample STREAM_NAME "$STREAM_NAME"
