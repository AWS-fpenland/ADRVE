#!/bin/bash
# ADRVE - Edge Device Setup Script

set -e

# Configuration variables
PROJECT_NAME="adrve"
REGION="us-east-1"  # Change to your preferred region
STACK_NAME="${PROJECT_NAME}-stack"
THING_NAME="${PROJECT_NAME}-edge-device"
CERTS_DIR="$HOME/certs"

# Check for AWS CLI
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is required but not installed. Please install it first."
    exit 1
fi

# Create certificates directory if it doesn't exist
mkdir -p $CERTS_DIR

echo "Setting up ADRVE Edge Device..."
echo "Region: $REGION"
echo "Thing Name: $THING_NAME"
echo "Certificates Directory: $CERTS_DIR"

# Check if stack exists
echo "Checking for CloudFormation stack..."
aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION > /dev/null || {
    echo "Stack $STACK_NAME does not exist in region $REGION. Please deploy the CloudFormation stack first."
    exit 1
}

# Get IoT policy name from stack outputs
IOT_POLICY=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='IoTPolicyName'].OutputValue" --output text)

if [ -z "$IOT_POLICY" ]; then
    echo "Could not find IoT policy in stack outputs."
    exit 1
fi

echo "Found IoT Policy: $IOT_POLICY"

# Create IoT thing
echo "Creating IoT thing..."
aws iot create-thing --thing-name $THING_NAME --region $REGION || {
    echo "Thing may already exist, continuing..."
}

# Create and download certificates
echo "Creating certificates..."
CERT_ARN=$(aws iot create-keys-and-certificate \
    --set-as-active \
    --certificate-pem-outfile "${CERTS_DIR}/${THING_NAME}.cert.pem" \
    --public-key-outfile "${CERTS_DIR}/${THING_NAME}.public.key" \
    --private-key-outfile "${CERTS_DIR}/${THING_NAME}.private.key" \
    --region $REGION \
    --query "certificateArn" \
    --output text)

# Download root CA certificate
echo "Downloading root CA certificate..."
curl -s https://www.amazontrust.com/repository/AmazonRootCA1.pem > "${CERTS_DIR}/root-CA.crt"

# Attach policy to certificate
echo "Attaching policy to certificate..."
aws iot attach-policy --policy-name $IOT_POLICY --target $CERT_ARN --region $REGION

# Attach certificate to thing
echo "Attaching certificate to thing..."
aws iot attach-thing-principal --thing-name $THING_NAME --principal $CERT_ARN --region $REGION

# Get IoT endpoint
IOT_ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --region $REGION --query "endpointAddress" --output text)

# Get Kinesis Video Stream name
KVS_STREAM=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='VideoStreamName'].OutputValue" --output text)

# Create config file for edge device
echo "Creating configuration file..."
cat > edge-device-config.json << EOL
{
    "region": "$REGION",
    "iotEndpoint": "$IOT_ENDPOINT",
    "iotCertPath": "${CERTS_DIR}/${THING_NAME}.cert.pem",
    "iotPrivateKeyPath": "${CERTS_DIR}/${THING_NAME}.private.key",
    "iotRootCAPath": "${CERTS_DIR}/root-CA.crt",
    "thingName": "$THING_NAME",
    "topicPrefix": "$PROJECT_NAME",
    "streamName": "$KVS_STREAM",
    "frameWidth": 1280,
    "frameHeight": 720,
    "fps": 15
}
EOL

# Install required Python packages
echo "Installing required Python packages..."
pip install ultralytics opencv-python boto3 AWSIoTPythonSDK awscrt

# Clone Kinesis Video Streams Producer SDK
echo "Cloning Kinesis Video Streams Producer SDK..."
if [ ! -d "amazon-kinesis-video-streams-producer-sdk-cpp" ]; then
    git clone https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp.git
    
    # Build the SDK
    echo "Building Kinesis Video Streams Producer SDK..."
    cd amazon-kinesis-video-streams-producer-sdk-cpp
    mkdir -p build
    cd build
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        cmake .. -DBUILD_GSTREAMER_PLUGIN=ON
    else
        # Linux
        cmake .. -DBUILD_GSTREAMER_PLUGIN=ON
    fi
    
    make
    cd ../..
fi

# Download YOLOv11 model
echo "Downloading YOLOv11 model..."
python -c "from ultralytics import YOLO; YOLO('yolov11n.pt')"

echo ""
echo "==================================================================="
echo "ADRVE Edge Device setup complete!"
echo "==================================================================="
echo ""
echo "Configuration:"
echo "  Thing Name: $THING_NAME"
echo "  IoT Endpoint: $IOT_ENDPOINT"
echo "  Certificates: $CERTS_DIR"
echo "  Kinesis Video Stream: $KVS_STREAM"
echo ""
echo "Next steps:"
echo "1. Update edge-device.py script with your configuration"
echo "2. Set up OBS Studio for video capture"
echo "3. Run the edge device script: python edge-device.py"
echo ""
echo "For more details, refer to the YOLOv11 Setup Guide."
