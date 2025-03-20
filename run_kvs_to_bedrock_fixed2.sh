#!/bin/bash

# Script to run the KVS to Bedrock integration with fixed script
# Usage: ./run_kvs_to_bedrock_fixed2.sh [--continuous] [--interval SECONDS] [--method METHOD]

# Default values
CONTINUOUS=false
INTERVAL=10
METHOD="media"  # Changed default to media since it's more reliable

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --continuous)
      CONTINUOUS=true
      shift
      ;;
    --interval)
      INTERVAL="$2"
      shift 2
      ;;
    --method)
      METHOD="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./run_kvs_to_bedrock_fixed2.sh [--continuous] [--interval SECONDS] [--method METHOD]"
      echo "Methods: media (default), clip, hls"
      exit 1
      ;;
  esac
done

# Set AWS profile
export AWS_PROFILE=org-master
export AWS_REGION=us-west-2

echo "Using AWS Profile: $AWS_PROFILE"
echo "AWS Region: $AWS_REGION"

# Check if AWS credentials are valid
echo "Checking AWS credentials..."
aws sts get-caller-identity > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Error: AWS credentials are not valid or expired"
  exit 1
fi
echo "AWS credentials are valid"

# Install required packages if not already installed
echo "Checking required Python packages..."
pip install opencv-python boto3 numpy pillow --quiet

# Run the KVS to Bedrock script
if [ "$CONTINUOUS" = true ]; then
  echo "Running in continuous mode with interval: $INTERVAL seconds, method: $METHOD"
  python kvs_to_bedrock_fixed2.py --continuous --interval $INTERVAL --method $METHOD
else
  echo "Running in single-frame mode with method: $METHOD"
  python kvs_to_bedrock_fixed2.py --method $METHOD
fi
