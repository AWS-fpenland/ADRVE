# ADRVE - Autonomous Delivery Robot Vision Enhancement

## Overview

ADRVE (Autonomous Delivery Robot Vision Enhancement) is a proof-of-concept (POC) solution that enhances the vision capabilities of autonomous delivery robots using AWS cloud services. The system processes video streams from robots, detects objects using AI/ML, and enables real-time decision making to improve safety and operational efficiency.

## Architecture

![ADRVE Architecture](architecture-diagram.png)

*Note: Create an architecture diagram and place it in the repository root.*

### Key Components

- **Edge Device**: Autonomous delivery robot with camera and local processing capabilities
- **Cloud Processing**: AWS services for advanced vision processing and decision making
- **Operator Interface**: Web application for monitoring and controlling robots

### AWS Services Used

- **Amazon Kinesis Video Streams**: For ingesting and processing video streams
- **Amazon S3**: For storing video frames and web application assets
- **Amazon DynamoDB**: For storing detection results and commands
- **AWS Lambda**: For serverless processing of video frames and business logic
- **Amazon Bedrock**: For AI-powered object detection and scene understanding
- **AWS IoT Core**: For secure communication with edge devices
- **Amazon API Gateway**: For RESTful API endpoints
- **Amazon CloudFront**: For content delivery of the web application
- **Amazon Cognito**: For authentication and authorization

## Deployment

### Prerequisites

- AWS CLI installed and configured with appropriate permissions
- An AWS account with access to all required services
- Sufficient service quotas for the resources defined in the template

### Deployment Steps

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd ADRVE
   ```

2. Deploy the CloudFormation stack:
   ```bash
   aws cloudformation create-stack \
     --stack-name adrve-stack \
     --template-body file://cloudformation-main.yaml \
     --capabilities CAPABILITY_IAM \
     --parameters \
       ParameterKey=ProjectName,ParameterValue=adrve \
       ParameterKey=OperatorEmail,ParameterValue=your-email@example.com
   ```

3. Monitor the stack creation:
   ```bash
   aws cloudformation describe-stacks --stack-name adrve-stack
   ```

4. Once deployment is complete, retrieve the outputs:
   ```bash
   aws cloudformation describe-stacks --stack-name adrve-stack --query "Stacks[0].Outputs"
   ```

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| ProjectName | Name prefix for all project resources | adrve |
| OperatorEmail | Email address for notifications | user@domain.com |
| VideoStreamResolution | Resolution of the video stream | 1280x720 |
| VideoStreamFrameRate | Frame rate of the video stream | 15 |
| BedrockModelId | Amazon Bedrock model for inference | anthropic.claude-3-sonnet-20240229-v1:0 |
| FrameExtractionRate | Frames per second to extract for cloud processing | 3 |

## Solution Components

### Storage Resources

- **VideoFramesBucket**: S3 bucket for storing extracted video frames
  - Includes lifecycle policy to delete frames after 7 days
  - CORS configuration for web access

- **WebAppBucket**: S3 bucket for hosting the web application
  - Configured for static website hosting
  - Protected by CloudFront distribution

- **DynamoDB Tables**:
  - **DetectionsTable**: Stores object detection results with TTL
  - **CommandsTable**: Stores commands sent to edge devices with TTL

### Processing Resources

- **FrameProcessorFunction**: Lambda function that processes video frames
  - Extracts frames from Kinesis Video Stream
  - Uses Amazon Bedrock for object detection
  - Stores results in DynamoDB
  - Sends commands to edge devices when necessary

- **KVSProcessorFunction**: Lambda function that processes Kinesis Video Stream fragments
  - Triggered periodically to extract frames
  - Invokes FrameProcessorFunction for each frame

- **GetDetectionsFunction**: Lambda function that retrieves detection results
  - Provides API for the web application
  - Generates presigned URLs for frame images

- **SendCommandFunction**: Lambda function that sends commands to edge devices
  - Stores commands in DynamoDB
  - Publishes commands to IoT topics

### Web Application

The solution includes a web application for operators to:
- View live video streams from robots
- See object detection overlays in real-time
- Send commands to robots (stop, resume, etc.)
- View detection history and command history

The web application is hosted on S3 and delivered via CloudFront for low-latency global access.

### Security

- **IAM Roles and Policies**: Least privilege access for all components
- **Cognito Identity Pool**: For web application authentication
- **IoT Policies**: For secure device communication
- **CloudFront Origin Access Control**: For protecting S3 content

## Edge Device Integration

To integrate an edge device with this solution:

1. Register the device with AWS IoT Core
2. Attach the IoT policy to the device certificate
3. Install the edge software (provided separately)
4. Configure the device with the appropriate endpoints and credentials

## Monitoring and Maintenance

- CloudWatch Logs are configured for all Lambda functions
- CloudWatch Metrics can be used to monitor system performance
- The web application provides real-time status of the system

## Limitations and Future Enhancements

This solution is a proof-of-concept and has the following limitations:

- Simplified video frame extraction (production would use proper video processing)
- Basic object detection logic (could be enhanced with more sophisticated models)
- Simulated video playback in the web application (production would use WebRTC)
- Limited error handling and retry logic

Future enhancements could include:

- Multi-device support with device management
- Enhanced AI/ML models for better object detection
- Edge-cloud collaboration for real-time processing
- Integration with routing and navigation systems
- Advanced analytics and reporting

## Cleanup

To delete all resources created by this solution:

```bash
aws cloudformation delete-stack --stack-name adrve-stack
```

Note: This will delete all resources including S3 buckets and their contents.

## License

[Specify your license information here]

## Contact

[Your contact information]
