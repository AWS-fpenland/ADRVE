#!/bin/bash

# Correct KVS test based on source code analysis
# This script tests the KVS producer with the correct parameters

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

# Create log configuration file
cat > "$KVS_DIR/../kvs_log_configuration" << EOF
log4cplus.rootLogger=DEBUG, KvsConsoleAppender

#KvsConsoleAppender:
log4cplus.appender.KvsConsoleAppender=log4cplus::ConsoleAppender
log4cplus.appender.KvsConsoleAppender.layout=log4cplus::PatternLayout
log4cplus.appender.KvsConsoleAppender.layout.ConversionPattern=[%-5p] [%d{%d-%m-%Y %H:%M:%S:%Q %Z}] %m%n
EOF

echo "Log configuration created at $KVS_DIR/../kvs_log_configuration"

# Set environment variables
export AWS_ACCESS_KEY_ID="$ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$SECRET_KEY"
if [ ! -z "$SESSION_TOKEN" ]; then
    export AWS_SESSION_TOKEN="$SESSION_TOKEN"
fi
export AWS_DEFAULT_REGION="$AWS_REGION"

# Run KVS producer with correct parameters
cd "$KVS_DIR"
echo "Running KVS producer with correct parameters..."

# Based on source code analysis, the first argument should be the stream name
# Additional parameters are passed as -w WIDTH -h HEIGHT -f FRAMERATE
./kvs_gstreamer_sample "$STREAM_NAME" -w 640 -h 480 -f 15
