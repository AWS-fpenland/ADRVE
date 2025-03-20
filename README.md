# ADRVE - Autonomous Delivery Robot Vision Enhancement

This project implements a vision enhancement system for autonomous delivery robots using AWS services including Kinesis Video Streams, Lambda, Bedrock, and IoT.

## Architecture

The system consists of the following components:

1. **Edge Device**: Captures video and streams it to AWS Kinesis Video Streams
2. **Kinesis Video Streams**: Stores and processes the video stream
3. **Lambda Functions**:
   - `fragment-processor`: Processes KVS fragments and triggers frame extraction
   - `frame-processor`: Extracts frames and processes them with Bedrock
4. **Amazon Bedrock**: Performs object detection on video frames
5. **DynamoDB**: Stores detection results
6. **S3**: Stores extracted video frames
7. **IoT Core**: Sends commands to edge devices

## Deployment

### Prerequisites

- AWS CLI installed and configured
- Python 3.9 or later
- pip package manager

### Steps to Deploy

1. **Clone the repository**:
   ```
   git clone <repository-url>
   cd ADRVE
   ```

2. **Update configuration**:
   Edit the `deploy.sh` script to set your:
   - AWS region
   - S3 bucket name
   - Operator email

3. **Deploy the stack**:
   ```
   ./deploy.sh
   ```

   This script will:
   - Package the Lambda functions
   - Create the OpenCV layer
   - Upload the packages to S3
   - Deploy the CloudFormation stack

4. **Verify deployment**:
   After deployment completes, the script will output the stack resources.

## Testing

### Testing with a Local Video File

1. **Extract a frame from a video file**:
   ```
   python extract_frame.py <video_file> test_frame.jpg
   ```

2. **Process the frame with Bedrock**:
   ```
   python test_image_to_bedrock_fixed.py --image test_frame.jpg --output test_detection.jpg --store
   ```

### Testing with KVS

1. **Upload a test video to KVS**:
   ```
   python upload_test_video.py --video <video_file> --stream adrve-video-stream
   ```

2. **Process frames from KVS**:
   ```
   python kvs_to_bedrock_final.py --video <video_file>
   ```

## Lambda Functions

### Frame Processor

The frame processor Lambda function:
- Extracts frames from KVS fragments
- Processes frames with Bedrock for object detection
- Stores frames in S3 and detection results in DynamoDB
- Sends commands to edge devices when critical objects are detected

### Fragment Processor

The fragment processor Lambda function:
- Receives notifications about new KVS fragments
- Invokes the frame processor Lambda for each fragment

## CloudFormation Resources

The CloudFormation template creates:
- S3 buckets for video frames and web application
- Kinesis Video Stream
- DynamoDB table for detections
- Lambda functions for processing
- IAM roles and policies
- IoT resources for edge device communication

## Customization

You can customize the system by modifying:
- The Bedrock model ID in the CloudFormation parameters
- The frame extraction rate
- The object detection logic in the frame processor Lambda
- The command logic for edge devices
