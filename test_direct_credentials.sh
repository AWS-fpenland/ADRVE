#!/bin/bash

# Test script to directly use AWS credentials
# Usage: ./test_direct_credentials.sh [profile_name]

# Default profile if not provided
PROFILE=${1:-"org-master"}
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

# Try multiple methods to get credentials
echo "Trying multiple methods to get AWS credentials..."

# Method 1: Use AWS CLI to get credentials
echo "Method 1: Using AWS CLI debug output..."
TEMP_CRED_FILE=$(mktemp)
AWS_DEBUG=1 aws s3 ls --profile $PROFILE > /dev/null 2> $TEMP_CRED_FILE

echo "Debug output preview:"
head -30 $TEMP_CRED_FILE

# Extract credentials from the debug output
ACCESS_KEY_1=$(grep -o "aws_access_key_id = [A-Z0-9]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)
SECRET_KEY_1=$(grep -o "aws_secret_access_key = [A-Za-z0-9/+]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)
SESSION_TOKEN_1=$(grep -o "aws_session_token = [A-Za-z0-9/+=]*" $TEMP_CRED_FILE | head -1 | cut -d' ' -f3)

# Clean up
rm $TEMP_CRED_FILE

echo "Method 1 results:"
echo "Access Key: ${ACCESS_KEY_1:-"Not found"}"
echo "Secret Key: ${SECRET_KEY_1:+Found}"
echo "Session Token: ${SESSION_TOKEN_1:+Found}"

# Method 2: Use AWS configure get
echo "Method 2: Using aws configure get..."
ACCESS_KEY_2=$(aws configure get aws_access_key_id --profile $PROFILE)
SECRET_KEY_2=$(aws configure get aws_secret_access_key --profile $PROFILE)
SESSION_TOKEN_2=$(aws configure get aws_session_token --profile $PROFILE)

echo "Method 2 results:"
echo "Access Key: ${ACCESS_KEY_2:-"Not found"}"
echo "Secret Key: ${SECRET_KEY_2:+Found}"
echo "Session Token: ${SESSION_TOKEN_2:+Found}"

# Method 3: Use AWS STS get-session-token
echo "Method 3: Using aws sts get-session-token..."
TEMP_CREDS=$(aws sts get-session-token --duration-seconds 3600 --profile $PROFILE 2>/dev/null)
if [ $? -eq 0 ]; then
    ACCESS_KEY_3=$(echo $TEMP_CREDS | jq -r '.Credentials.AccessKeyId')
    SECRET_KEY_3=$(echo $TEMP_CREDS | jq -r '.Credentials.SecretAccessKey')
    SESSION_TOKEN_3=$(echo $TEMP_CREDS | jq -r '.Credentials.SessionToken')
    
    echo "Method 3 results:"
    echo "Access Key: ${ACCESS_KEY_3:-"Not found"}"
    echo "Secret Key: ${SECRET_KEY_3:+Found}"
    echo "Session Token: ${SESSION_TOKEN_3:+Found}"
else
    echo "Method 3 failed: Cannot call get-session-token with SSO credentials"
fi

# Method 4: Use AWS STS assume-role
echo "Method 4: Using aws sts assume-role..."
CALLER_IDENTITY=$(aws sts get-caller-identity --profile $PROFILE)
ROLE_ARN=$(echo $CALLER_IDENTITY | jq -r '.Arn')
ACCOUNT_ID=$(echo $CALLER_IDENTITY | jq -r '.Account')

if [[ $ROLE_ARN == *"assumed-role"* ]]; then
    ROLE_NAME=$(echo $ROLE_ARN | cut -d'/' -f2)
    TEMP_CREDS=$(aws sts assume-role --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}" --role-session-name "KVSTest" --profile $PROFILE 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        ACCESS_KEY_4=$(echo $TEMP_CREDS | jq -r '.Credentials.AccessKeyId')
        SECRET_KEY_4=$(echo $TEMP_CREDS | jq -r '.Credentials.SecretAccessKey')
        SESSION_TOKEN_4=$(echo $TEMP_CREDS | jq -r '.Credentials.SessionToken')
        
        echo "Method 4 results:"
        echo "Access Key: ${ACCESS_KEY_4:-"Not found"}"
        echo "Secret Key: ${SECRET_KEY_4:+Found}"
        echo "Session Token: ${SESSION_TOKEN_4:+Found}"
    else
        echo "Method 4 failed: Cannot assume role"
    fi
else
    echo "Method 4 skipped: Not using an assumed role"
fi

# Choose the best available credentials
if [ ! -z "$ACCESS_KEY_1" ] && [ ! -z "$SECRET_KEY_1" ]; then
    ACCESS_KEY=$ACCESS_KEY_1
    SECRET_KEY=$SECRET_KEY_1
    SESSION_TOKEN=$SESSION_TOKEN_1
    echo "Using credentials from Method 1"
elif [ ! -z "$ACCESS_KEY_2" ] && [ ! -z "$SECRET_KEY_2" ]; then
    ACCESS_KEY=$ACCESS_KEY_2
    SECRET_KEY=$SECRET_KEY_2
    SESSION_TOKEN=$SESSION_TOKEN_2
    echo "Using credentials from Method 2"
elif [ ! -z "$ACCESS_KEY_3" ] && [ ! -z "$SECRET_KEY_3" ]; then
    ACCESS_KEY=$ACCESS_KEY_3
    SECRET_KEY=$SECRET_KEY_3
    SESSION_TOKEN=$SESSION_TOKEN_3
    echo "Using credentials from Method 3"
elif [ ! -z "$ACCESS_KEY_4" ] && [ ! -z "$SECRET_KEY_4" ]; then
    ACCESS_KEY=$ACCESS_KEY_4
    SECRET_KEY=$SECRET_KEY_4
    SESSION_TOKEN=$SESSION_TOKEN_4
    echo "Using credentials from Method 4"
else
    echo "Failed to obtain AWS credentials from any method. Exiting."
    exit 1
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

echo "Credential file created at $KVS_PRODUCER_PATH/.kvs/credential"
cat $KVS_PRODUCER_PATH/.kvs/credential | grep -v "secret"

# Export credentials for environment
export AWS_ACCESS_KEY_ID=$ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$SECRET_KEY
if [ ! -z "$SESSION_TOKEN" ]; then
    export AWS_SESSION_TOKEN=$SESSION_TOKEN
fi
export AWS_DEFAULT_REGION="us-west-2"

echo "AWS credentials set up successfully"
