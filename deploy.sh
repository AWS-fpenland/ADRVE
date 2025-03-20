#!/bin/bash

# Script to deploy the ADRVE stack
# This script packages and deploys the Lambda functions and CloudFormation stack

# Set variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="${SCRIPT_DIR}/lambda_deployment"
STACK_NAME="adrve-stack"
REGION="us-west-2"
BUCKET_NAME="adrve-video-frames-056689112963"  # Replace with your bucket name
OPERATOR_EMAIL="user@domain.com"  # Replace with your email

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Package Lambda functions
echo "Packaging Lambda functions..."
bash "${SCRIPT_DIR}/package_lambdas.sh"

# Create OpenCV layer
echo "Creating OpenCV layer..."
mkdir -p "${DEPLOYMENT_DIR}/opencv-layer/python"
pip install opencv-python-headless numpy -t "${DEPLOYMENT_DIR}/opencv-layer/python" --no-cache-dir
cd "${DEPLOYMENT_DIR}/opencv-layer" && zip -r "${DEPLOYMENT_DIR}/opencv-layer.zip" python > /dev/null

# Upload Lambda packages and layer to S3
echo "Uploading Lambda packages and layer to S3..."
aws s3 cp "${DEPLOYMENT_DIR}/frame_processor.zip" "s3://${BUCKET_NAME}/lambda/frame_processor.zip" --region "${REGION}"
aws s3 cp "${DEPLOYMENT_DIR}/fragment_processor.zip" "s3://${BUCKET_NAME}/lambda/fragment_processor.zip" --region "${REGION}"
aws s3 cp "${DEPLOYMENT_DIR}/opencv-layer.zip" "s3://${BUCKET_NAME}/layers/opencv-layer.zip" --region "${REGION}"

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/updated_cloudformation.yaml" \
    --stack-name "${STACK_NAME}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        ProjectName=adrve \
        OperatorEmail="${OPERATOR_EMAIL}" \
        VideoStreamResolution="1280x720" \
        VideoStreamFrameRate=15 \
        BedrockModelId="anthropic.claude-3-sonnet-20240229-v1:0" \
        FrameExtractionRate=3 \
    --region "${REGION}"

# Check if deployment was successful
if [ $? -eq 0 ]; then
    echo "Deployment successful!"
    
    # Get stack outputs
    echo "Stack outputs:"
    aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs" \
        --output table \
        --region "${REGION}"
else
    echo "Deployment failed."
    exit 1
fi
