#!/bin/bash

# Script to run the KVS to Bedrock integration
# Usage: ./run_kvs_to_bedrock.sh [--continuous] [--interval SECONDS]

# Default values
CONTINUOUS=false
INTERVAL=10

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
    *)
      echo "Unknown option: $1"
      echo "Usage: ./run_kvs_to_bedrock.sh [--continuous] [--interval SECONDS]"
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

# Run the KVS to Bedrock script
if [ "$CONTINUOUS" = true ]; then
  echo "Running in continuous mode with interval: $INTERVAL seconds"
  python kvs_to_bedrock.py --continuous --interval $INTERVAL
else
  echo "Running in single-frame mode"
  python kvs_to_bedrock.py
fi
