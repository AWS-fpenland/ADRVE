#!/bin/bash

# Script to update the Cognito Identity Pool to allow unauthenticated access
# This is a temporary fix until you can update the CloudFormation stack

IDENTITY_POOL_ID="us-west-2:4979dca7-4346-43b6-b0bb-0822bf749cdb"
REGION="us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
VIDEO_STREAM_ARN="arn:aws:kinesisvideo:us-west-2:${ACCOUNT_ID}:stream/adrve-video-stream"
API_GATEWAY_ID=$(aws apigateway get-rest-apis --query "items[?name=='adrve-api'].id" --output text)

echo "Updating Cognito Identity Pool: $IDENTITY_POOL_ID"
echo "Video Stream ARN: $VIDEO_STREAM_ARN"
echo "API Gateway ID: $API_GATEWAY_ID"

# 1. Update the identity pool to allow unauthenticated access
echo "Enabling unauthenticated access..."
aws cognito-identity update-identity-pool \
  --identity-pool-id $IDENTITY_POOL_ID \
  --identity-pool-name "adrveIdentityPool" \
  --allow-unauthenticated-identities \
  --region $REGION

# 2. Create an IAM role for unauthenticated access
echo "Creating IAM role for unauthenticated access..."
ROLE_NAME="adrve-cognito-unauth-role"

# Create trust policy document
cat > trust-policy.json << EOL
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "cognito-identity.amazonaws.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "cognito-identity.amazonaws.com:aud": "$IDENTITY_POOL_ID"
        },
        "ForAnyValue:StringLike": {
          "cognito-identity.amazonaws.com:amr": "unauthenticated"
        }
      }
    }
  ]
}
EOL

# Create policy document
cat > policy.json << EOL
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kinesisvideo:GetDataEndpoint",
        "kinesisvideo:GetMedia",
        "kinesisvideo:DescribeStream",
        "kinesisvideo:ListFragments",
        "kinesisvideo:GetHLSStreamingSessionURL",
        "kinesisvideo-archived-media:GetHLSStreamingSessionURL"
      ],
      "Resource": "$VIDEO_STREAM_ARN"
    },
    {
      "Effect": "Allow",
      "Action": [
        "execute-api:Invoke"
      ],
      "Resource": "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_GATEWAY_ID/*/GET/*"
    }
  ]
}
EOL

# Check if role exists
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$ROLE_ARN" ]; then
  # Create role
  echo "Creating new role: $ROLE_NAME"
  ROLE_ARN=$(aws iam create-role \
    --role-name $ROLE_NAME \
    --assume-role-policy-document file://trust-policy.json \
    --query 'Role.Arn' \
    --output text)
    
  # Attach policy to role
  aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name "adrve-unauth-policy" \
    --policy-document file://policy.json
else
  echo "Role already exists: $ROLE_NAME"
  # Update role trust policy
  aws iam update-assume-role-policy \
    --role-name $ROLE_NAME \
    --policy-document file://trust-policy.json
    
  # Update role policy
  aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name "adrve-unauth-policy" \
    --policy-document file://policy.json
fi

# 3. Get the authenticated role ARN
AUTH_ROLE_ARN=$(aws cognito-identity get-identity-pool-roles \
  --identity-pool-id $IDENTITY_POOL_ID \
  --query 'Roles.authenticated' \
  --output text \
  --region $REGION)

# 4. Set the roles for the identity pool
echo "Setting roles for identity pool..."
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id $IDENTITY_POOL_ID \
  --roles authenticated=$AUTH_ROLE_ARN,unauthenticated=$ROLE_ARN \
  --region $REGION

# Clean up temporary files
rm -f trust-policy.json policy.json

echo "Identity pool updated successfully!"
echo "You should now be able to access the KVS stream without authentication."
