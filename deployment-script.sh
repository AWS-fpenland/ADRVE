#!/bin/bash
# ADRVE - Autonomous Delivery Robot Vision Enhancement POC Deployment Script

set -e

# Configuration variables
PROJECT_NAME="adrve"
REGION="us-west-2"  # Change to your preferred region
STACK_NAME="${PROJECT_NAME}-stack"
TEMPLATE_FILE="cloudformation-main.yaml"
OPERATOR_EMAIL=""

# Check for AWS CLI
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is required but not installed. Please install it first."
    exit 1
fi

# Check if template file exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Error: CloudFormation template file $TEMPLATE_FILE not found."
    echo "Please ensure you have the template file in the current directory."
    exit 1
fi

# Check for valid region
aws ec2 describe-regions --region $REGION --query "Regions[?RegionName=='$REGION']" --output text > /dev/null || {
    echo "Invalid AWS region: $REGION"
    exit 1
}

# Get operator email if not provided
if [ -z "$OPERATOR_EMAIL" ]; then
    read -p "Enter operator email address: " OPERATOR_EMAIL
fi

# Validate email format
if [[ ! $OPERATOR_EMAIL =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
    echo "Invalid email format: $OPERATOR_EMAIL"
    exit 1
fi

echo "Deploying ADRVE to AWS..."
echo "Region: $REGION"
echo "Project Name: $PROJECT_NAME"
echo "Stack Name: $STACK_NAME"
echo "Operator Email: $OPERATOR_EMAIL"

# Validate CloudFormation template
echo "Validating CloudFormation template..."
aws cloudformation validate-template --template-body file://$TEMPLATE_FILE --region $REGION

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack..."
aws cloudformation create-stack \
    --stack-name $STACK_NAME \
    --template-body file://$TEMPLATE_FILE \
    --parameters \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
        ParameterKey=OperatorEmail,ParameterValue=$OPERATOR_EMAIL \
    --capabilities CAPABILITY_IAM \
    --region $REGION

echo "Stack creation initiated. Waiting for completion..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION

if [ $? -eq 0 ]; then
    echo "Stack creation completed successfully."
    
    # Get stack outputs
    echo "Retrieving stack outputs..."
    aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs" --output table
    
    # Extract CloudFront domain and API endpoint
    CLOUDFRONT_DOMAIN=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDomain'].OutputValue" --output text)
    API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)
    
    echo ""
    echo "==================================================================="
    echo "ADRVE deployment complete!"
    echo "Web Application URL: https://$CLOUDFRONT_DOMAIN"
    echo "API Endpoint: $API_ENDPOINT"
    echo "==================================================================="
    echo ""
    echo "Next steps:"
    echo "1. Configure your edge device using the provided script"
    echo "2. Set up AWS IoT certificates for edge device"
    echo "3. Install and configure YOLOv11 on your laptop"
    echo "4. Test the system by streaming video from your laptop"
else
    echo "Stack creation failed."
    aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $REGION --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}" --output table
fi