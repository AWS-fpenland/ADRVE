#!/bin/bash

# Script to deploy the frame processor Lambda container function

# Set variables
PROJECT_NAME="adrve"
REGION=$(aws configure get region --profile org-master)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile org-master)
ECR_REPOSITORY_NAME="frame-processor"
IMAGE_TAG="latest"

# Deploy the CloudFormation stack
echo "Deploying CloudFormation stack for Lambda container function..."
aws cloudformation deploy \
    --stack-name ${PROJECT_NAME}-lambda-container \
    --template-file cloudformation-lambda-container.yaml \
    --parameter-overrides \
        ProjectName=${PROJECT_NAME} \
        ECRRepositoryName=${ECR_REPOSITORY_NAME} \
        ECRImageTag=${IMAGE_TAG} \
    --capabilities CAPABILITY_NAMED_IAM \
    --profile org-master

# Check if deployment was successful
if [ $? -eq 0 ]; then
    echo "Deployment successful!"
    
    # Get the Lambda function ARN
    FUNCTION_ARN=$(aws cloudformation describe-stacks \
        --stack-name ${PROJECT_NAME}-lambda-container \
        --query "Stacks[0].Outputs[?OutputKey=='FrameProcessorFunctionArn'].OutputValue" \
        --output text \
        --profile org-master)
    
    echo "Lambda Function ARN: ${FUNCTION_ARN}"
    
    # Create a test event
    echo "Creating test event..."
    cat > /tmp/test-event.json << EOF
{
  "streamName": "${PROJECT_NAME}-video-stream",
  "fragmentNumber": "91343852333212752275675982790612275766161739294",
  "deviceId": "camera-001"
}
EOF
    
    echo "To test the function, run:"
    echo "aws lambda invoke --function-name ${PROJECT_NAME}-frame-processor --payload file:///tmp/test-event.json --cli-binary-format raw-in-base64-out /tmp/lambda-response.json --profile org-master"
else
    echo "Deployment failed!"
fi
