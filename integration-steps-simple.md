# Integration Steps for Containerized Frame Processor

## Step 1: Add ECR Repository to CloudFormation Template

Add the ECR repository resource to your CloudFormation template:

```yaml
# Add this to the Resources section of your CloudFormation template
FrameProcessorRepository:
  Type: AWS::ECR::Repository
  Properties:
    RepositoryName: !Sub "${ProjectName}-frame-processor"
    ImageScanningConfiguration:
      ScanOnPush: true
    LifecyclePolicy:
      LifecyclePolicyText: |
        {
          "rules": [
            {
              "rulePriority": 1,
              "description": "Keep only the last 5 images",
              "selection": {
                "tagStatus": "any",
                "countType": "imageCountMoreThan",
                "countNumber": 5
              },
              "action": {
                "type": "expire"
              }
            }
          ]
        }
```

## Step 2: Update the FrameProcessorFunction in CloudFormation Template

Replace the existing FrameProcessorFunction with the containerized version:

```yaml
FrameProcessorFunction:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub "${ProjectName}-frame-processor"
    Role: !GetAtt LambdaExecutionRole.Arn
    PackageType: Image
    Timeout: 60
    MemorySize: 1024
    Environment:
      Variables:
        FRAME_BUCKET: !Ref VideoFramesBucket
        DETECTION_TABLE: !Ref DetectionsTable
        BEDROCK_MODEL_ID: !Ref BedrockModelId
        IOT_TOPIC_PREFIX: !Ref ProjectName
    Code:
      ImageUri: !Sub "${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ProjectName}-frame-processor:latest"
```

## Step 3: Build and Push the Container Image

1. Prepare the container files in the `lambda_fixed/lambda-container/final` directory:
   - Dockerfile
   - lambda_function.py

2. Build and push the container image:

```bash
# Set variables
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile org-master)
REGION=$(aws configure get region --profile org-master)
REPOSITORY_NAME="adrve-frame-processor"
IMAGE_TAG="latest"

# Build the Docker image
cd lambda_fixed/lambda-container/final
docker build -t ${REPOSITORY_NAME}:${IMAGE_TAG} .

# Log in to ECR
aws ecr get-login-password --region ${REGION} --profile org-master | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Tag the image
docker tag ${REPOSITORY_NAME}:${IMAGE_TAG} ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}:${IMAGE_TAG}

# Push the image to ECR
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}:${IMAGE_TAG}
```

## Step 4: Deploy the Updated CloudFormation Stack

```bash
aws cloudformation deploy \
  --template-file cloudformation-main.yaml \
  --stack-name adrve \
  --parameter-overrides ProjectName=adrve BedrockModelId=anthropic.claude-3-sonnet-20240229-v1:0 \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile org-master
```

## Step 5: Test the Function

Test the function by invoking it with a test event:

```bash
aws lambda invoke \
  --function-name adrve-frame-processor \
  --payload '{"streamName":"adrve-video-stream","fragmentNumber":"12345","deviceId":"test-device"}' \
  --profile org-master \
  output.json
```
