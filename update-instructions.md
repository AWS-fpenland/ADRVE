# Instructions for Updating CloudFormation Template

To integrate the containerized frame processor function into your CloudFormation template while preserving all existing functionality, follow these steps:

## 1. Add ECR Repository Resource

Add the ECR repository resource to your CloudFormation template. This repository will store the container image for the frame processor function.

Open your CloudFormation template and add the ECR repository resource from the `ecr-repository.yaml` file to the Resources section.

## 2. Replace FrameProcessorFunction Definition

Replace the existing FrameProcessorFunction definition with the containerized version from the `frame-processor-update.yaml` file.

Find the FrameProcessorFunction resource in your CloudFormation template and replace it with the updated version.

## 3. Prepare Container Files

Ensure the container files are properly set up in the `lambda_fixed/lambda-container/final` directory:
- Dockerfile
- lambda_function.py

These files have already been created for you.

## 4. Build and Deploy

Follow the steps in the `integration-steps-simple.md` file to:
1. Build the container image
2. Push it to ECR
3. Deploy the updated CloudFormation stack

## Key Differences

The main differences between the original and containerized function are:

1. **Packaging**: Changed from inline code to container image
2. **Dependencies**: The container includes OpenCV and other dependencies needed for video frame processing
3. **Frame Extraction**: Enhanced frame extraction using OpenCV instead of the simplified approach in the original function
4. **Error Handling**: Improved error handling and logging

All environment variables, permissions, and core functionality remain the same.
