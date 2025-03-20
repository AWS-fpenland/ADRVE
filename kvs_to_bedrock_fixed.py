#!/usr/bin/env python3
"""
Script to extract frames from KVS and process them with Bedrock
"""

import os
import json
import boto3
import base64
import time
import cv2
import numpy as np
import argparse
from datetime import datetime
import uuid
import tempfile

# Constants
BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
STREAM_NAME = "adrve-video-stream"
BUCKET_NAME = "adrve-video-frames-056689112963"
DETECTION_TABLE = "adrve-detections"
IOT_TOPIC_PREFIX = "adrve"
DEVICE_ID = "adrve-edge-device"

def get_kvs_data_endpoint(stream_name, api_name):
    """Get the KVS data endpoint for the specified API"""
    kvs_client = boto3.client('kinesisvideo', region_name='us-west-2')
    response = kvs_client.get_data_endpoint(
        StreamName=stream_name,
        APIName=api_name
    )
    return response['DataEndpoint']

def extract_frame_from_kvs(stream_name):
    """Extract a frame from the KVS stream"""
    try:
        # Get the data endpoint for GetMedia API
        endpoint = get_kvs_data_endpoint(stream_name, 'GET_MEDIA')
        print(f"Using KVS endpoint: {endpoint}")
        
        # Create a client using the endpoint - use kinesisvideo-media client
        kvs_media_client = boto3.client('kinesisvideo-media', 
                                        endpoint_url=endpoint, 
                                        region_name='us-west-2')
        
        # Get media from the stream
        response = kvs_media_client.get_media(
            StreamName=stream_name,
            StartSelector={
                'StartSelectorType': 'NOW'
            }
        )
        
        # Create a temporary file to store the media fragment
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_path = temp_file.name
            
            # Read the payload in chunks
            payload = response['Payload']
            for chunk in payload:
                temp_file.write(chunk)
        
        print(f"Media fragment saved to temporary file: {temp_path}")
        
        # Use OpenCV to extract a frame from the video file
        cap = cv2.VideoCapture(temp_path)
        ret, frame = cap.read()
        cap.release()
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        if not ret:
            print("Failed to extract frame from video fragment")
            return None
            
        print(f"Successfully extracted frame with shape: {frame.shape}")
        return frame
            
    except Exception as e:
        print(f"Error extracting frame from KVS: {str(e)}")
        return None

def extract_frame_from_kvs_alternative(stream_name):
    """Alternative method to extract a frame using GetClip API"""
    try:
        # Get the data endpoint for GetClip API
        endpoint = get_kvs_data_endpoint(stream_name, 'GET_CLIP')
        print(f"Using KVS endpoint for GetClip: {endpoint}")
        
        # Create a client using the endpoint
        kvs_archived_client = boto3.client('kinesisvideo-archived-media', 
                                          endpoint_url=endpoint, 
                                          region_name='us-west-2')
        
        # Calculate time range (last 5 seconds)
        end_time = datetime.utcnow()
        start_time = end_time.replace(second=end_time.second-5)
        
        # Get clip from the stream
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_path = temp_file.name
            
            response = kvs_archived_client.get_clip(
                StreamName=stream_name,
                ClipFragmentSelector={
                    'FragmentSelectorType': 'SERVER_TIMESTAMP',
                    'TimestampRange': {
                        'StartTimestamp': start_time,
                        'EndTimestamp': end_time
                    }
                }
            )
            
            # Read the payload in chunks
            payload = response['Payload']
            for chunk in payload:
                temp_file.write(chunk)
        
        print(f"Clip saved to temporary file: {temp_path}")
        
        # Use OpenCV to extract a frame from the video file
        cap = cv2.VideoCapture(temp_path)
        ret, frame = cap.read()
        cap.release()
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        if not ret:
            print("Failed to extract frame from video clip")
            return None
            
        print(f"Successfully extracted frame with shape: {frame.shape}")
        return frame
            
    except Exception as e:
        print(f"Error extracting frame using GetClip: {str(e)}")
        return None

def extract_frame_from_hls(stream_name):
    """Extract a frame from the HLS stream"""
    try:
        # Get the data endpoint for HLS
        endpoint = get_kvs_data_endpoint(stream_name, 'GET_HLS_STREAMING_SESSION_URL')
        print(f"Using KVS endpoint for HLS: {endpoint}")
        
        # Create a client using the endpoint
        kvs_archived_client = boto3.client('kinesisvideo-archived-media', 
                                          endpoint_url=endpoint, 
                                          region_name='us-west-2')
        
        # Get HLS URL
        response = kvs_archived_client.get_hls_streaming_session_url(
            StreamName=stream_name,
            PlaybackMode='LIVE',
            HLSFragmentSelector={
                'FragmentSelectorType': 'SERVER_TIMESTAMP',
                'TimestampRange': {
                    'StartTimestamp': datetime.utcnow().replace(second=datetime.utcnow().second-30)
                }
            },
            ContainerFormat='FRAGMENTED_MP4',
            DiscontinuityMode='ALWAYS',
            DisplayFragmentTimestamp='NEVER',
            MaxMediaPlaylistFragmentResults=5,
            ExpireAfter=3600
        )
        
        hls_url = response['HLSStreamingSessionURL']
        print(f"HLS URL: {hls_url}")
        
        # Use OpenCV to capture a frame from the HLS stream
        cap = cv2.VideoCapture(hls_url)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            print("Failed to extract frame from HLS stream")
            return None
            
        print(f"Successfully extracted frame with shape: {frame.shape}")
        return frame
            
    except Exception as e:
        print(f"Error extracting frame from HLS: {str(e)}")
        return None

def detect_objects_with_bedrock(frame):
    """Detect objects in the frame using Amazon Bedrock with Claude model"""
    try:
        # Initialize Bedrock client
        bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')
        
        # Convert frame to JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        image_data = buffer.tobytes()
        
        # Encode as base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Create the payload for Claude
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Analyze this image from an urban street scene. Identify all humans, vehicles (cars, bikes, etc.), animals, and other potential obstacles. For each object, provide its location in the image (top, bottom, left, right) and confidence score. Format the response as JSON only with the following structure: {\"objects\": [{\"type\": \"person\", \"confidence\": 0.95, \"box\": [x1, y1, x2, y2]}, ...]}"
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
        
        # Call Bedrock
        print("Calling Bedrock with Claude model...")
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(payload)
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        content = response_body.get('content', [{}])[0].get('text', '{}')
        
        # Try to extract JSON from the response
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_content = content[json_start:json_end]
            try:
                detection_data = json.loads(json_content)
                return detection_data
            except json.JSONDecodeError:
                print("Failed to parse JSON from Claude's response")
                print("Raw response:", content)
                return {"objects": []}
        else:
            print("No JSON found in Claude's response")
            print("Raw response:", content)
            return {"objects": []}
    
    except Exception as e:
        print(f"Error in Bedrock detection: {str(e)}")
        return {"objects": [], "error": str(e)}

def store_frame_and_detection(frame, detection_data, timestamp):
    """Store frame in S3 and detection results in DynamoDB"""
    try:
        # Generate unique ID for this frame
        frame_id = str(uuid.uuid4())
        
        # Save frame to S3
        s3_client = boto3.client('s3', region_name='us-west-2')
        
        # Convert frame to JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        image_data = buffer.tobytes()
        
        # Create S3 key
        frame_key = f"frames/{datetime.utcfromtimestamp(timestamp).strftime('%Y/%m/%d/%H')}/" + \
                   f"{timestamp}_{frame_id}.jpg"
        
        # Upload to S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=frame_key,
            Body=image_data,
            ContentType='image/jpeg'
        )
        
        print(f"Frame uploaded to S3: {BUCKET_NAME}/{frame_key}")
        
        # Add metadata to detection data
        detection_data['timestamp'] = timestamp
        detection_data['source'] = 'cloud'
        
        # Store detection results in DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        table = dynamodb.Table(DETECTION_TABLE)
        
        item = {
            'frameId': frame_id,
            'timestamp': int(timestamp),
            'frameS3Path': frame_key,
            'detectionResults': detection_data,
            'ttl': int(timestamp) + (7 * 24 * 60 * 60)  # 7 days TTL
        }
        
        table.put_item(Item=item)
        print(f"Detection results stored in DynamoDB with frameId: {frame_id}")
        
        return frame_id
    
    except Exception as e:
        print(f"Error storing frame and detection: {str(e)}")
        return None

def send_command_to_edge(detection_data, device_id):
    """Send command to edge device if necessary"""
    # Simple logic: if humans or animals detected with high confidence, send stop command
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
            iot_client = boto3.client('iot-data', region_name='us-west-2')
            topic = f"{IOT_TOPIC_PREFIX}/commands/{device_id}"
            
            iot_client.publish(
                topic=topic,
                payload=json.dumps(command)
            )
            
            print(f"Stop command sent to {topic} due to {', '.join(critical_objects)}")
            return True
    
    except Exception as e:
        print(f"Error sending command: {str(e)}")
    
    return False

def draw_boxes(frame, detection_data):
    """Draw bounding boxes on the frame based on detection results"""
    try:
        # Make a copy of the frame
        output_frame = frame.copy()
        
        # Draw boxes for each detected object
        for obj in detection_data.get('objects', []):
            # Get box coordinates
            box = obj.get('box', [0, 0, 100, 100])
            if len(box) == 4:
                x1, y1, x2, y2 = [int(coord) for coord in box]
                
                # Draw rectangle
                cv2.rectangle(output_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                
                # Draw label
                label = f"{obj.get('type', 'unknown')} ({obj.get('confidence', 0):.2f})"
                cv2.putText(output_frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        return output_frame
        
    except Exception as e:
        print(f"Error drawing boxes: {str(e)}")
        return frame

def main():
    parser = argparse.ArgumentParser(description='Extract frames from KVS and process with Bedrock')
    parser.add_argument('--output', default='kvs_frame.jpg', help='Path for the output image')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=10, help='Interval between frames in seconds')
    parser.add_argument('--method', choices=['media', 'clip', 'hls'], default='hls', 
                        help='Method to extract frames: media (GetMedia), clip (GetClip), or hls (HLS)')
    args = parser.parse_args()
    
    try:
        if args.continuous:
            print(f"Running continuously with {args.interval} second interval using {args.method} method...")
            while True:
                # Extract frame from KVS using the specified method
                if args.method == 'media':
                    frame = extract_frame_from_kvs(STREAM_NAME)
                elif args.method == 'clip':
                    frame = extract_frame_from_kvs_alternative(STREAM_NAME)
                else:  # hls
                    frame = extract_frame_from_hls(STREAM_NAME)
                
                if frame is not None:
                    # Get current timestamp
                    timestamp = time.time()
                    
                    # Detect objects
                    detection_data = detect_objects_with_bedrock(frame)
                    
                    # Store frame and detection results
                    frame_id = store_frame_and_detection(frame, detection_data, timestamp)
                    
                    # Send command to edge if necessary
                    command_sent = send_command_to_edge(detection_data, DEVICE_ID)
                    
                    # Draw boxes on the frame
                    output_frame = draw_boxes(frame, detection_data)
                    
                    # Save the frame
                    output_path = f"kvs_frame_{int(timestamp)}.jpg"
                    cv2.imwrite(output_path, output_frame)
                    print(f"Frame with detection boxes saved to {output_path}")
                    
                    # Print summary
                    print(f"Processed frame at {datetime.fromtimestamp(timestamp)}")
                    print(f"Detected {len(detection_data.get('objects', []))} objects")
                    print(f"Frame ID: {frame_id}")
                    print(f"Command sent: {command_sent}")
                    print("-" * 50)
                else:
                    print("Failed to extract frame from KVS, will retry...")
                
                # Wait for the next interval
                time.sleep(args.interval)
        else:
            # Extract a single frame using the specified method
            print(f"Extracting a single frame using {args.method} method...")
            if args.method == 'media':
                frame = extract_frame_from_kvs(STREAM_NAME)
            elif args.method == 'clip':
                frame = extract_frame_from_kvs_alternative(STREAM_NAME)
            else:  # hls
                frame = extract_frame_from_hls(STREAM_NAME)
            
            if frame is not None:
                # Save the raw frame
                cv2.imwrite(args.output, frame)
                print(f"Frame extracted from KVS and saved to {args.output}")
                
                # Get current timestamp
                timestamp = time.time()
                
                # Detect objects
                detection_data = detect_objects_with_bedrock(frame)
                
                # Print detection results
                print("\nDetection Results:")
                print(json.dumps(detection_data, indent=2))
                
                # Store frame and detection results
                frame_id = store_frame_and_detection(frame, detection_data, timestamp)
                print(f"Frame ID: {frame_id}")
                
                # Draw boxes on the frame
                output_frame = draw_boxes(frame, detection_data)
                
                # Save the frame with boxes
                output_path = f"kvs_detection_{int(timestamp)}.jpg"
                cv2.imwrite(output_path, output_frame)
                print(f"Frame with detection boxes saved to {output_path}")
            else:
                print("Failed to extract frame from KVS")
    
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
