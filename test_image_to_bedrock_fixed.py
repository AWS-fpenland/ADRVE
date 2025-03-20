#!/usr/bin/env python3
"""
Test script to process a local image with Bedrock
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
from decimal import Decimal

# Constants
BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
BUCKET_NAME = "adrve-video-frames-056689112963"
DETECTION_TABLE = "adrve-detections"

# Helper class to convert float to Decimal for DynamoDB
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, float):
            return Decimal(str(obj))
        return super(DecimalEncoder, self).default(obj)

def detect_objects_with_bedrock(image_path):
    """Detect objects in the image using Amazon Bedrock with Claude model"""
    try:
        # Read the image
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Error: Could not read image {image_path}")
            return None, None
        
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
                return frame, detection_data
            except json.JSONDecodeError:
                print("Failed to parse JSON from Claude's response")
                print("Raw response:", content)
                return frame, {"objects": []}
        else:
            print("No JSON found in Claude's response")
            print("Raw response:", content)
            return frame, {"objects": []}
    
    except Exception as e:
        print(f"Error in Bedrock detection: {str(e)}")
        return None, {"objects": [], "error": str(e)}

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
        detection_data['timestamp'] = int(timestamp)
        detection_data['source'] = 'cloud'
        
        # Convert float values to Decimal for DynamoDB
        detection_data_str = json.dumps(detection_data)
        detection_data_decimal = json.loads(detection_data_str, parse_float=Decimal)
        
        # Store detection results in DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        table = dynamodb.Table(DETECTION_TABLE)
        
        item = {
            'frameId': frame_id,
            'timestamp': int(timestamp),
            'frameS3Path': frame_key,
            'detectionResults': detection_data_decimal,
            'ttl': int(timestamp) + (7 * 24 * 60 * 60)  # 7 days TTL
        }
        
        table.put_item(Item=item)
        print(f"Detection results stored in DynamoDB with frameId: {frame_id}")
        
        return frame_id
    
    except Exception as e:
        print(f"Error storing frame and detection: {str(e)}")
        return None

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
    parser = argparse.ArgumentParser(description='Process a local image with Bedrock')
    parser.add_argument('--image', required=True, help='Path to the input image')
    parser.add_argument('--output', default='detection_output.jpg', help='Path for the output image with boxes')
    parser.add_argument('--store', action='store_true', help='Store results in S3 and DynamoDB')
    args = parser.parse_args()
    
    try:
        # Process the image with Bedrock
        frame, detection_data = detect_objects_with_bedrock(args.image)
        
        if frame is not None:
            # Print detection results
            print("\nDetection Results:")
            print(json.dumps(detection_data, indent=2))
            
            # Store frame and detection results if requested
            if args.store:
                timestamp = time.time()
                frame_id = store_frame_and_detection(frame, detection_data, timestamp)
                print(f"Frame ID: {frame_id}")
            
            # Draw boxes on the frame
            output_frame = draw_boxes(frame, detection_data)
            
            # Save the frame with boxes
            cv2.imwrite(args.output, output_frame)
            print(f"Frame with detection boxes saved to {args.output}")
        else:
            print("Failed to process image")
    
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
