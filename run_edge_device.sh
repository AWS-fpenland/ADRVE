#!/bin/bash

# Run the edge device script with AWS SSO profile
# This script handles AWS SSO login and runs the edge device script

# Configuration
PROFILE="org-master"
SCRIPT_PATH="/mnt/c/code/ADRVE/ADRVE/edge-device-script.py"

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

# Run the edge device script
echo "Starting edge device script with profile: $PROFILE"
python3 $SCRIPT_PATH --profile $PROFILE
