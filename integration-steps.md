# Integration Steps for Containerized Frame Processor

This document outlines the steps to integrate the containerized `frame-processor` Lambda function into the ADRVE solution.

## Overview

The existing solution uses a standard Lambda function with inline code for the frame processor. We're replacing it with a containerized version that has better support for OpenCV and other dependencies needed for video frame processing.

## Prerequisites

1. AWS CLI configured with the `org-master` profile
2. Docker installed and running
3. Access to the AWS account where the solution is deployed

## Integration Steps

### 1. Create the ECR Repository

First, we need to create an ECR repository to store our container image:

```bash
aws cloudformation deploy \
  --template-file cloudformation-container.yaml \
  --stack-name adrve-container \
  --parameter-overrides ProjectName=adrve \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile org-master
```

### 2. Build and Push the Container Image

Navigate to the `lambda_fixed/lambda-container/final` directory and build the Docker image:

```bash
cd lambda_fixed/lambda-container/final
docker build -t adrve-frame-processor:latest .
```

Get the ECR login credentials:

```bash
aws ecr get-login-password --region us-west-2 --profile org-master | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text --profile org-master).dkr.ecr.us-west-2.amazonaws.com
```

Tag and push the image:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile org-master)
docker tag adrve-frame-processor:latest ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/adrve-frame-processor:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/adrve-frame-processor:latest
```

### 3. Update the CloudFormation Template

Replace the existing CloudFormation template with the updated version:

```bash
cp cloudformation-main-updated.yaml cloudformation-main.yaml
```

### 4. Deploy the Updated CloudFormation Stack

Deploy the updated CloudFormation stack:

```bash
aws cloudformation deploy \
  --template-file cloudformation-main.yaml \
  --stack-name adrve \
  --parameter-overrides ProjectName=adrve BedrockModelId=anthropic.claude-3-sonnet-20240229-v1:0 \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile org-master
```

## Key Changes

1. **Lambda Function Type**: Changed from a standard Lambda function with inline code to a containerized function using an ECR image.

2. **Dependencies**: The container includes OpenCV and other dependencies needed for video frame processing.

3. **Frame Processing Logic**: Enhanced frame extraction and processing capabilities:
   - Uses OpenCV to extract frames from video fragments
   - Properly handles temporary files
   - Improved error handling and logging

4. **Integration with Bedrock**: The containerized function uses Amazon Bedrock with Claude 3 Sonnet for object detection in images.

5. **CloudFormation Updates**:
   - Modified the `FrameProcessorFunction` resource to use a container image
   - Added reference to the ECR repository

## Testing

After deployment, you can test the function by invoking it with a test event:

```bash
aws lambda invoke \
  --function-name adrve-frame-processor \
  --payload '{"streamName":"adrve-video-stream","fragmentNumber":"12345","deviceId":"test-device"}' \
  --profile org-master \
  output.json
```

## Rollback Plan

If issues occur, you can roll back to the previous version by:

1. Reverting to the previous CloudFormation template
2. Redeploying the stack

```bash
# Restore from backup (if available)
cp cloudformation-main.yaml.bak cloudformation-main.yaml

# Redeploy
aws cloudformation deploy \
  --template-file cloudformation-main.yaml \
  --stack-name adrve \
  --parameter-overrides ProjectName=adrve BedrockModelId=anthropic.claude-3-sonnet-20240229-v1:0 \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile org-master
```
