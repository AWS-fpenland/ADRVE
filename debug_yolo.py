#!/usr/bin/env python3
"""
Debug script to test YOLO detection for ADRVE
"""

import cv2
import time
import sys
from ultralytics import YOLO

# YOLO Configuration
YOLO_MODEL_PATH = "yolo11n.pt"  # Will be downloaded if not present
CONFIDENCE_THRESHOLD = 0.3

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_yolo.py <video_file>")
        sys.exit(1)
        
    video_file = sys.argv[1]
    
    # Initialize YOLO model
    print("Loading YOLO model...")
    try:
        model = YOLO(YOLO_MODEL_PATH)
        print("YOLO model loaded successfully")
    except Exception as e:
        print(f"Failed to load YOLO model: {str(e)}")
        sys.exit(1)
    
    # Open video file
    print(f"Opening video file: {video_file}")
    cap = cv2.VideoCapture(video_file)
    
    if not cap.isOpened():
        print(f"Failed to open video file: {video_file}")
        sys.exit(1)
    
    # Process first 10 frames
    for i in range(10):
        ret, frame = cap.read()
        if not ret:
            print("End of video file reached")
            break
            
        print(f"\nProcessing frame {i+1}...")
        start_time = time.time()
        
        # Run YOLO detection
        results = model(frame, conf=CONFIDENCE_THRESHOLD)
        
        # Process results
        detections = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = model.names[cls]
                
                detection = {
                    "box": [float(x1), float(y1), float(x2), float(y2)],
                    "class": class_name,
                    "class_id": cls,
                    "confidence": conf
                }
                detections.append(detection)
        
        # Print detection summary
        elapsed = time.time() - start_time
        print(f"Frame processed in {elapsed:.2f} seconds")
        print(f"Detected {len(detections)} objects:")
        for i, det in enumerate(detections):
            print(f"  {i+1}. {det['class']} (ID: {det['class_id']}) - Confidence: {det['confidence']:.2f}")
    
    # Clean up
    cap.release()
    print("\nYOLO detection test completed")

if __name__ == "__main__":
    main()
