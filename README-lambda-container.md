# ADRVE Lambda Container Integration

This guide explains how to deploy the frame processor Lambda function using a container image from your existing ECR repository.

## Prerequisites

1. An ECR repository with the frame processor container image
2. The container image should have the necessary code to process frames from Kinesis Video Streams
3. AWS CLI configured with appropriate permissions

## Files

- `cloudformation-lambda-container.yaml`: CloudFormation template for deploying the Lambda function
- `deploy-lambda-container.sh`: Script to deploy the CloudFormation stack

## Deployment Steps

1. Make sure your container image is pushed to ECR:
   ```bash
   # Build and push the container image if needed
   cd lambda_fixed/lambda-container/final
   docker build -t frame-processor:latest .
   aws ecr get-login-password --region us-west-2 --profile org-master | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-west-2.amazonaws.com
   docker tag frame-processor:latest <account-id>.dkr.ecr.us-west-2.amazonaws.com/frame-processor:latest
   docker push <account-id>.dkr.ecr.us-west-2.amazonaws.com/frame-processor:latest
   ```

2. Deploy the Lambda function:
   ```bash
   ./deploy-lambda-container.sh
   ```

3. Test the Lambda function:
   ```bash
   aws lambda invoke \
     --function-name adrve-frame-processor \
     --payload file:///tmp/test-event.json \
     --cli-binary-format raw-in-base64-out \
     /tmp/lambda-response.json \
     --profile org-master
   ```

## CloudFormation Template

The CloudFormation template (`cloudformation-lambda-container.yaml`) creates:

1. An IAM role with permissions for:
   - S3 (to store frames)
   - DynamoDB (to store detection results)
   - Kinesis Video Streams (to access video streams)
   - Bedrock (to perform object detection)
   - IoT (to publish notifications)

2. A Lambda function that:
   - Uses your container image from ECR
   - Has the necessary environment variables
   - Has appropriate timeout and memory settings

## Environment Variables

The Lambda function uses the following environment variables:

- `FRAME_BUCKET`: S3 bucket for storing frames
- `DETECTION_TABLE`: DynamoDB table for storing detection results
- `BEDROCK_MODEL_ID`: Bedrock model ID for object detection
- `IOT_TOPIC_PREFIX`: Prefix for IoT topics

## Integration with Existing Resources

The Lambda function integrates with your existing resources:

- Uses the existing S3 bucket for storing frames
- Uses the existing DynamoDB table for storing detection results
- Processes frames from the existing Kinesis Video Stream
- Publishes notifications to IoT topics with your project name as prefix

## Customization

You can customize the deployment by modifying the parameters in the CloudFormation template:

- `ProjectName`: Name for the project resources (default: adrve)
- `BedrockModelId`: Amazon Bedrock model to use for inference (default: anthropic.claude-3-sonnet-20240229-v1:0)
- `ECRRepositoryName`: Name of the existing ECR repository (default: frame-processor)
- `ECRImageTag`: Tag of the container image to deploy (default: latest)
