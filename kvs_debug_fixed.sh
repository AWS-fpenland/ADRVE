#!/bin/bash

# Debug script for KVS producer with fixed parameter passing
# This script runs the KVS producer directly with verbose output

# Configuration
PROFILE="org-master"
KVS_DIR="/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"
STREAM_NAME="adrve-video-stream"
AWS_REGION="us-west-2"

# Check if AWS SSO session is active
echo "Checking AWS SSO session..."
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

# Get AWS credentials
echo "Getting AWS credentials..."
ACCESS_KEY=$(aws configure get aws_access_key_id --profile $PROFILE)
SECRET_KEY=$(aws configure get aws_secret_access_key --profile $PROFILE)
SESSION_TOKEN=$(aws configure get aws_session_token --profile $PROFILE)

if [ -z "$ACCESS_KEY" ] || [ -z "$SECRET_KEY" ]; then
    echo "Failed to get AWS credentials. Using boto3 to get credentials..."
    
    # Create a Python script to get credentials
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
fi

# Create .kvs directory in KVS build directory
mkdir -p "$KVS_DIR/../.kvs"

# Create credential file
echo "Creating credential file..."
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

# Create log directory
mkdir -p "$KVS_DIR/log"

# Create log configuration file
cat > "$KVS_DIR/kvs_log_configuration" << EOF
log4cplus.rootLogger=DEBUG, KvsConsoleAppender

#KvsConsoleAppender:
log4cplus.appender.KvsConsoleAppender=log4cplus::ConsoleAppender
log4cplus.appender.KvsConsoleAppender.layout=log4cplus::PatternLayout
log4cplus.appender.KvsConsoleAppender.layout.ConversionPattern=[%-5p] [%d{%d-%m-%Y %H:%M:%S:%Q %Z}] %m%n
EOF

echo "Log configuration created at $KVS_DIR/kvs_log_configuration"

# Set environment variables
export AWS_ACCESS_KEY_ID="$ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$SECRET_KEY"
if [ ! -z "$SESSION_TOKEN" ]; then
    export AWS_SESSION_TOKEN="$SESSION_TOKEN"
fi
export KVSSINK_LOG_CONFIG_PATH="$KVS_DIR/kvs_log_configuration"
export KVSSINK_VERBOSE_LOGGING=1

# Run KVS producer with properly quoted parameters
echo "Running KVS producer..."
cd "$KVS_DIR"

# IMPORTANT: The parameters need to be passed as a single string with quotes
# This is the key fix for the HTTP 400 error
./kvs_gstreamer_sample \
    "AWS_REGION=$AWS_REGION" \
    "STREAM_NAME=$STREAM_NAME" \
    "VIDEO_WIDTH=640" \
    "VIDEO_HEIGHT=480" \
    "VIDEO_FPS=15" \
    "RETENTION_PERIOD=2" \
    "LOG_CONFIG_PATH=$KVS_DIR/kvs_log_configuration"
