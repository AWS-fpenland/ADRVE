#!/usr/bin/env python3
"""
Test script for Amazon Bedrock object detection with Claude model
"""

import os
import json
import boto3
import base64
import argparse
from PIL import Image, ImageDraw
import io

# Constants
BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

def detect_objects_with_bedrock(image_path):
    """Detect objects in an image using Amazon Bedrock with Claude model"""
    try:
        # Initialize Bedrock client
        bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')
        
        # Read and encode the image
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
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
        # Claude sometimes includes markdown code blocks or extra text
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

def draw_boxes(image_path, detection_data, output_path):
    """Draw bounding boxes on the image based on detection results"""
    try:
        # Open the image
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        
        # Draw boxes for each detected object
        for obj in detection_data.get('objects', []):
            # Get box coordinates
            box = obj.get('box', [0, 0, 100, 100])
            if len(box) == 4:
                x1, y1, x2, y2 = box
                
                # Draw rectangle
                draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
                
                # Draw label
                label = f"{obj.get('type', 'unknown')} ({obj.get('confidence', 0):.2f})"
                draw.text((x1, y1-15), label, fill="red")
        
        # Save the image with boxes
        image.save(output_path)
        print(f"Image with detection boxes saved to {output_path}")
        
    except Exception as e:
        print(f"Error drawing boxes: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Test Amazon Bedrock object detection')
    parser.add_argument('--image', required=True, help='Path to the input image')
    parser.add_argument('--output', default='detection_output.jpg', help='Path for the output image with boxes')
    args = parser.parse_args()
    
    # Detect objects
    detection_data = detect_objects_with_bedrock(args.image)
    
    # Print detection results
    print("\nDetection Results:")
    print(json.dumps(detection_data, indent=2))
    
    # Draw boxes on the image
    draw_boxes(args.image, detection_data, args.output)

if __name__ == "__main__":
    main()
