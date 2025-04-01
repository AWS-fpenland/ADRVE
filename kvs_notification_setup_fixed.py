import boto3
import json
import cfnresponse
import time
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Set up KVS stream notification to Kinesis Data Stream
    
    This function is used as a CloudFormation custom resource to create
    a notification configuration for a Kinesis Video Stream that sends
    notifications to a Kinesis Data Stream.
    
    Args:
        event (dict): CloudFormation custom resource event
        context (object): Lambda context object
        
    Returns:
        None: Response is sent via cfnresponse
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Handle DELETE request
        if event['RequestType'] == 'Delete':
            logger.info("Delete request - sending success response")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            return
        
        # Get parameters from the event
        stream_name = event['ResourceProperties']['VideoStreamName']
        notification_stream_arn = event['ResourceProperties']['NotificationStreamArn']
        
        logger.info(f"Setting up notification for stream {stream_name} to {notification_stream_arn}")
        
        # Configure KVS stream notification
        kvs_client = boto3.client('kinesisvideo')
        
        # Wait for the stream to be active
        max_retries = 10
        retries = 0
        while retries < max_retries:
            try:
                logger.info(f"Checking stream status (attempt {retries+1}/{max_retries})")
                response = kvs_client.describe_stream(StreamName=stream_name)
                
                if response['StreamInfo']['Status'] == 'ACTIVE':
                    logger.info("Stream is active, proceeding with notification setup")
                    break
                    
                logger.info(f"Stream status is {response['StreamInfo']['Status']}, waiting...")
                retries += 1
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error checking stream status: {str(e)}")
                retries += 1
                time.sleep(5)
        
        if retries >= max_retries:
            logger.warning("Max retries reached waiting for stream to be active")
        
        # Configure notification using the correct method name and parameter structure
        logger.info("Creating stream notification configuration")
        response = kvs_client.update_notification_configuration(
            StreamName=stream_name,
            NotificationConfiguration={
                'DestinationConfig': {
                    'Uri': notification_stream_arn
                }
            }
        )
        
        logger.info(f"Notification configuration created successfully: {json.dumps(response)}")
        
        # Send success response
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {
            'Status': 'Notification configuration created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {
            'Error': str(e)
        })
