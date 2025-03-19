#!/bin/bash

# Fixed run script for edge device
# This script sets up the environment and runs the edge device script

# Configuration
PROFILE="org-master"
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

# Create .kvs directory
mkdir -p .kvs

# Create credential file
cat > .kvs/credential << EOF
{
  "accessKeyId": "$ACCESS_KEY",
  "secretAccessKey": "$SECRET_KEY"
EOF

if [ ! -z "$SESSION_TOKEN" ]; then
    echo "  ,\"sessionToken\": \"$SESSION_TOKEN\"" >> .kvs/credential
fi

echo "}" >> .kvs/credential

echo "Credential file created at .kvs/credential"

# Set environment variables
export AWS_ACCESS_KEY_ID="$ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$SECRET_KEY"
if [ ! -z "$SESSION_TOKEN" ]; then
    export AWS_SESSION_TOKEN="$SESSION_TOKEN"
fi
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PROFILE="$PROFILE"

# Run the edge device script
echo "Running edge device script..."
python3 edge-device-script.py
