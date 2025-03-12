import os
import json
import uuid
import time
import boto3
import base64
from datetime import datetime

s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
iot_client = boto3.client('iot-data')

# Get environment variables
BUCKET_NAME = os.environ['FRAME_BUCKET']
DETECTION_TABLE = os.environ['DETECTION_TABLE']
BEDROCK_MODEL_ID = os.environ['BEDROCK_MODEL_ID']
IOT_TOPIC_PREFIX = os.environ['IOT_TOPIC_PREFIX']

def extract_frame(kvs_client, stream_name, fragment_number):
    """Extract a frame from Kinesis Video Stream"""
    try:
        # Get the media for the specific fragment
        response = kvs_client.get_media(
            StreamName=stream_name,
            StartSelector={
                'StartSelectorType': 'FRAGMENT_NUMBER',
                'AfterFragmentNumber': fragment_number
            }
        )
        
        # For simplicity in POC, we're assuming we can extract a frame from the fragment
        # In a production system, we would use a proper video frame extractor
        payload = response['Payload'].read()
        
        # For POC purposes, we're just taking a section of the payload as our "frame"
        # In production, you would use OpenCV or similar to properly extract the frame
        frame_data = payload[:1024*1024]  # Example - first MB of data
        
        return frame_data
    except Exception as e:
        print(f"Error extracting frame: {str(e)}")
        return None

def detect_objects_with_bedrock(frame_data, timestamp):
    """Detect objects in the frame using Bedrock"""
    try:
        # For the POC, we'll use base64 encoded image with Claude model
        # In production, you might use a specialized computer vision model
        
        base64_image = base64.b64encode(frame_data).decode('utf-8')
        
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Analyze this image from an urban street scene. Identify all humans, vehicles (cars, bikes, etc.), animals, and other potential obstacles. For each object, provide its location in the image (top, bottom, left, right) and confidence score. Format the response as JSON only."
                        },
                        {
                            "type": "image", 
                            "source": {
                                "type": "base64", 
                                "media_type": "image/jpeg", 
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        }
        
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(payload)
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract the JSON content from Claude's response
        # This is a simplified approach - production code would need more robust parsing
        content = response_body.get('content', [{}])[0].get('text', '{}')
        
        # Try to parse the JSON from Claude's response
        try:
            detection_data = json.loads(content)
        except json.JSONDecodeError:
            # If Claude didn't return valid JSON, create a basic structure
            detection_data = {"objects": [], "error": "Failed to parse model output"}
        
        # Add metadata
        detection_data['timestamp'] = timestamp
        detection_data['source'] = 'cloud'
        
        return detection_data
    
    except Exception as e:
        print(f"Error in Bedrock detection: {str(e)}")
        return {
            "objects": [],
            "error": str(e),
            "timestamp": timestamp,
            "source": "cloud"
        }

def store_frame_and_detection(frame_data, detection_data, timestamp):
    """Store frame in S3 and detection results in DynamoDB"""
    try:
        # Generate unique ID for this frame
        frame_id = str(uuid.uuid4())
        
        # Save frame to S3
        frame_key = f"frames/{datetime.utcfromtimestamp(timestamp).strftime('%Y/%m/%d/%H')}/" + \
                   f"{timestamp}_{frame_id}.jpg"
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=frame_key,
            Body=frame_data,
            ContentType='image/jpeg'
        )
        
        # Store detection results in DynamoDB
        table = dynamodb.Table(DETECTION_TABLE)
        
        item = {
            'frameId': frame_id,
            'timestamp': int(timestamp),
            'frameS3Path': frame_key,
            'detectionResults': detection_data,
            'ttl': int(timestamp) + (7 * 24 * 60 * 60)  # 7 days TTL
        }
        
        table.put_item(Item=item)
        
        return frame_id
    
    except Exception as e:
        print(f"Error storing frame and detection: {str(e)}")
        return None

def send_command_to_edge(detection_data, device_id):
    """Send command to edge device if necessary"""
    # Simple logic: if humans or animals detected with high confidence, send stop command
    # In production, this would be more sophisticated
    
    try:
        # Check for objects of interest
        should_stop = False
        critical_objects = []
        
        for obj in detection_data.get('objects', []):
            object_type = obj.get('type', '').lower()
            confidence = obj.get('confidence', 0)
            
            if (object_type in ['human', 'person', 'pedestrian', 'animal', 'dog', 'cat']) and confidence > 0.7:
                should_stop = True
                critical_objects.append(object_type)
        
        if should_stop:
            command = {
                'command': 'stop',
                'reason': f"Critical objects detected: {', '.join(critical_objects)}",
                'timestamp': int(time.time())
            }
            
            # Publish to IoT topic
            topic = f"{IOT_TOPIC_PREFIX}/commands/{device_id}"
            iot_client.publish(
                topic=topic,
                payload=json.dumps(command)
            )
            
            return True
    
    except Exception as e:
        print(f"Error sending command: {str(e)}")
    
    return False

def lambda_handler(event, context):
    """Main Lambda handler function"""
    # In a real implementation, this would be triggered by Kinesis Data Stream
    # For POC purposes, we assume the event contains:
    # - streamName: The Kinesis Video Stream name
    # - fragmentNumber: The fragment to process
    # - deviceId: The edge device ID
    
    try:
        stream_name = event.get('streamName')
        fragment_number = event.get('fragmentNumber')
        device_id = event.get('deviceId')
        
        if not all([stream_name, fragment_number, device_id]):
            return {
                'statusCode': 400,
                'body': json.dumps('Missing required parameters')
            }
        
        # Get KVS client
        kvs_client = boto3.client('kinesisvideo')
        data_endpoint_response = kvs_client.get_data_endpoint(
            StreamName=stream_name,
            APIName='GET_MEDIA'
        )
        
        endpoint = data_endpoint_response['DataEndpoint']
        kvs_client = boto3.client('kinesisvideo', endpoint_url=endpoint)
        
        # Current timestamp
        timestamp = int(time.time())
        
        # Extract frame
        frame_data = extract_frame(kvs_client, stream_name, fragment_number)
        if not frame_data:
            return {
                'statusCode': 500,
                'body': json.dumps('Failed to extract frame')
            }
        
        # Detect objects
        detection_data = detect_objects_with_bedrock(frame_data, timestamp)
        
        # Store frame and detection results
        frame_id = store_frame_and_detection(frame_data, detection_data, timestamp)
        
        # Send command to edge if necessary
        command_sent = send_command_to_edge(detection_data, device_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'frameId': frame_id,
                'commandSent': command_sent,
                'objectsDetected': len(detection_data.get('objects', []))
            })
        }
    
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
