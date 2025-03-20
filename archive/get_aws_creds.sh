#!/bin/bash

# Script to extract AWS credentials from an AWS profile and export them as environment variables
# Usage: source ./get_aws_creds.sh [profile_name]

# Default profile if not provided
PROFILE=${1:-"org-master"}

echo "Extracting AWS credentials from profile: $PROFILE"

# Check if AWS SSO session is active
aws sts get-caller-identity --profile $PROFILE &> /dev/null
if [ $? -ne 0 ]; then
    echo "AWS SSO session not active or expired. Logging in..."
    aws sso login --profile $PROFILE
    
    # Check if login was successful
    if [ $? -ne 0 ]; then
        echo "Failed to log in with AWS SSO. Exiting."
        return 1
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
AWS_DEBUG=1 aws s3 ls --profile $PROFILE > /dev/null 2> $TEMP_CRED_FILE

# Extract credentials from the debug output
ACCESS_KEY=$(grep -o "aws_access_key_id = [A-Z0-9]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)
SECRET_KEY=$(grep -o "aws_secret_access_key = [A-Za-z0-9/+]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)
SESSION_TOKEN=$(grep -o "aws_session_token = [A-Za-z0-9/+=]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)

# Clean up
rm $TEMP_CRED_FILE

# Verify we have credentials
if [ -z "$ACCESS_KEY" ] || [ -z "$SECRET_KEY" ]; then
    echo "Failed to obtain AWS credentials. Exiting."
    return 1
fi

# Export credentials as environment variables
export AWS_ACCESS_KEY_ID=$ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$SECRET_KEY
if [ ! -z "$SESSION_TOKEN" ]; then
    export AWS_SESSION_TOKEN=$SESSION_TOKEN
fi
export AWS_DEFAULT_REGION="us-west-2"

echo "AWS credentials exported to environment variables:"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:5}..."
echo "AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:0:5}..."
if [ ! -z "$AWS_SESSION_TOKEN" ]; then
    echo "AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN:0:5}..."
fi
echo "AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"

echo "You can now run the test scripts that use environment variables:"
echo "  ./test_rtsp_env_creds.sh [rtsp_url]"
echo "  ./test_rtmp_env_creds.sh [rtmp_url]"
