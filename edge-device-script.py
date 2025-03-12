#!/usr/bin/env python3
"""
ADRVE Edge Device Script
------------------------
This script integrates:
1. OBS Studio for video capture
2. YOLOv11 for local object detection
3. AWS Kinesis Video Streams for cloud streaming
4. AWS IoT Core for command reception

Requirements:
- Python 3.8+
- ultralytics package (pip install ultralytics)
- boto3 (pip install boto3)
- AWSIoTPythonSDK (pip install AWSIoTPythonSDK)
- opencv-python (pip install opencv-python)
- Amazon Kinesis Video Streams Producer SDK (requires separate installation)

Before running, configure AWS credentials and update the CONFIG section.
"""

import os
import sys
import time
import json
import threading
import queue
import cv2
import numpy as np
import boto3
import subprocess
from datetime import datetime
from ultralytics import YOLO
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# ==================== CONFIG ====================
# AWS Configuration
AWS_REGION = "us-east-1"  # Update with your region
IOT_ENDPOINT = "your-iot-endpoint.iot.us-east-1.amazonaws.com"  # Get from AWS IoT Core console
IOT_CERT_PATH = "~/certs/edge-device.cert.pem"
IOT_PRIVATE_KEY_PATH = "~/certs/edge-device.private.key"
IOT_ROOT_CA_PATH = "~/certs/root-CA.crt"
IOT_THING_NAME = "adrve-edge-device"
IOT_TOPIC_PREFIX = "adrve"

# Video Configuration
STREAM_NAME = "adrve-video-stream"
VIDEO_DEVICE = 0  # Usually 0 for primary webcam
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FPS = 15
KVS_PRODUCER_PATH = "~/amazon-kinesis-video-streams-producer-sdk-cpp/build"

# YOLO Configuration
YOLO_MODEL_PATH = "yolov11n.pt"  # Will be downloaded if not present
CONFIDENCE_THRESHOLD = 0.3
# Classes we're particularly interested in (subset of COCO)
CLASSES_OF_INTEREST = [
    0,   # person
    1,   # bicycle
    2,   # car
    3,   # motorcycle
    5,   # bus
    6,   # train
    7,   # truck
    16,  # dog
    17,  # cat
    18,  # horse
]

# ==================== GLOBAL VARIABLES ====================
# Frame queue for YOLO processing
frame_queue = queue.Queue(maxsize=10)
# Detection results queue
detection_queue = queue.Queue()
# Flag to control threads
running = True
# Current commands from cloud
cloud_commands = {}

# ==================== YOLO MODEL ====================
def initialize_yolo():
    """Initialize and return YOLO model"""
    print("Initializing YOLOv11 model...")
    try:
        model = YOLO(YOLO_MODEL_PATH)
        print("YOLO model loaded successfully")
        return model
    except Exception as e:
        print(f"Failed to load YOLO model: {str(e)}")
        sys.exit(1)

def yolo_detection_thread(model):
    """Thread to run YOLO detection on frames"""
    print("Starting YOLO detection thread")
    while running:
        try:
            if not frame_queue.empty():
                frame_data = frame_queue.get()
                if frame_data is None:
                    continue
                
                frame, timestamp = frame_data
                results = model(frame, conf=CONFIDENCE_THRESHOLD)
                
                detections = []
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0]
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        
                        # If the class is in our list of interest, and confidence exceeds threshold
                        if cls in CLASSES_OF_INTEREST and conf > CONFIDENCE_THRESHOLD:
                            class_name = model.names[cls]
                            detection = {
                                "box": [float(x1), float(y1), float(x2), float(y2)],
                                "class": class_name,
                                "class_id": cls,
                                "confidence": conf
                            }
                            detections.append(detection)
                
                # Put results in the detection queue
                detection_result = {
                    "timestamp": timestamp,
                    "detections": detections,
                    "source": "edge"
                }
                detection_queue.put((frame, detection_result))
            else:
                time.sleep(0.01)  # Brief pause if no frames
        except Exception as e:
            print(f"Error in YOLO detection thread: {str(e)}")
            time.sleep(1)  # Pause on error before retrying

# ==================== AWS IoT ====================
def initialize_iot():
    """Initialize and return AWS IoT client"""
    print("Initializing AWS IoT Client...")
    try:
        client = AWSIoTMQTTClient(IOT_THING_NAME)
        client.configureEndpoint(IOT_ENDPOINT, 8883)
        client.configureCredentials(IOT_ROOT_CA_PATH, IOT_PRIVATE_KEY_PATH, IOT_CERT_PATH)
        
        # Configure connection settings
        client.configureAutoReconnectBackoffTime(1, 32, 20)
        client.configureOfflinePublishQueueing(-1)  # Infinite queueing
        client.configureDrainingFrequency(2)  # 2 Hz
        client.configureConnectDisconnectTimeout(10)
        client.configureMQTTOperationTimeout(5)
        
        # Connect
        client.connect()
        print("IoT client connected successfully")
        return client
    except Exception as e:
        print(f"Failed to initialize IoT client: {str(e)}")
        return None

def setup_iot_subscriptions(client):
    """Setup IoT topic subscriptions"""
    def command_callback(client, userdata, message):
        """Callback for command messages"""
        try:
            payload = json.loads(message.payload.decode('utf-8'))
            command = payload.get('command')
            timestamp = payload.get('timestamp')
            
            # Store in global commands dict
            cloud_commands[timestamp] = payload
            
            print(f"Received command: {command}")
            
            # Process command (simple version for POC)
            if command == 'stop':
                print("STOP COMMAND RECEIVED - would halt robot in production")
                # In a real robot, this would trigger emergency stop
        except Exception as e:
            print(f"Error processing command: {str(e)}")
    
    # Subscribe to commands topic
    command_topic = f"{IOT_TOPIC_PREFIX}/commands/{IOT_THING_NAME}"
    client.subscribe(command_topic, 1, command_callback)
    print(f"Subscribed to topic: {command_topic}")

def publish_detection(client, detection):
    """Publish detection to IoT Core"""
    try:
        topic = f"{IOT_TOPIC_PREFIX}/status/{IOT_THING_NAME}/detection"
        client.publish(topic, json.dumps(detection), 0)
    except Exception as e:
        print(f"Error publishing detection: {str(e)}")

# ==================== VIDEO STREAMING ====================
def start_kvs_producer():
    """Start the Kinesis Video Stream producer as a separate process"""
    try:
        # Build command for the KVS producer
        # This assumes the KVS C++ producer SDK is installed and built
        kvs_command = [
            f"{KVS_PRODUCER_PATH}/kvs_gstreamer_sample",
            f"AWS_REGION={AWS_REGION}",
            f"STREAM_NAME={STREAM_NAME}",
            f"VIDEO_WIDTH={FRAME_WIDTH}",
            f"VIDEO_HEIGHT={FRAME_HEIGHT}",
            f"VIDEO_FPS={FPS}",
            "RETENTION_PERIOD=2"  # 2 hours retention
        ]
        
        # Start process
        process = subprocess.Popen(
            kvs_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"Started KVS producer with PID: {process.pid}")
        return process
    except Exception as e:
        print(f"Failed to start KVS producer: {str(e)}")
        return None

def capture_video():
    """Capture video from camera and feed both to YOLO and the KVS producer"""
    try:
        print(f"Opening video device {VIDEO_DEVICE}")
        cap = cv2.VideoCapture(VIDEO_DEVICE)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, FPS)
        
        if not cap.isOpened():
            print("Failed to open video device")
            sys.exit(1)
        
        print("Video capture started")
        last_fps_time = time.time()
        frame_count = 0
        
        while running:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame")
                time.sleep(0.1)
                continue
            
            timestamp = time.time()
            frame_count += 1
            
            # Calculate FPS every second
            if time.time() - last_fps_time > 1:
                fps = frame_count / (time.time() - last_fps_time)
                print(f"Capture FPS: {fps:.2f}")
                frame_count = 0
                last_fps_time = time.time()
            
            # Put frame in queue for YOLO processing
            if not frame_queue.full():
                frame_queue.put((frame.copy(), timestamp))
            
            # In POC, we assume the KVS producer captures from the same video device
            # In production, we would send the frame to the KVS producer
            
            # Display frame with detection overlay (if available)
            display_frame = frame.copy()
            
            # Add detection boxes if available
            if not detection_queue.empty():
                _, detection_data = detection_queue.get()
                
                # Draw bounding boxes for edge detections
                for det in detection_data.get("detections", []):
                    box = det.get("box")
                    if box:
                        x1, y1, x2, y2 = map(int, box)
                        confidence = det.get("confidence", 0)
                        class_name = det.get("class", "unknown")
                        
                        # Draw box (green for edge detections)
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        # Add label
                        label = f"{class_name}: {confidence:.2f}"
                        cv2.putText(display_frame, label, (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Show any cloud commands
            for ts, cmd in list(cloud_commands.items()):
                # Display recent commands (last 3 seconds)
                if time.time() - ts < 3:
                    command = cmd.get("command", "")
                    reason = cmd.get("reason", "")
                    
                    # Display command on frame (red for stop commands)
                    if command == "stop":
                        cv2.putText(display_frame, f"CLOUD: {command} - {reason}", 
                                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                else:
                    # Remove old commands
                    cloud_commands.pop(ts, None)
            
            # Display timestamp
            cv2.putText(display_frame, f"Time: {datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Show the frame
            cv2.imshow("ADRVE Edge Device", display_frame)
            
            # Check for exit key
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Exit requested")
                global running
                running = False
                break
        
        # Clean up
        cap.release()
        cv2.destroyAllWindows()
    
    except Exception as e:
        print(f"Error in video capture: {str(e)}")
        global running
        running = False

# ==================== MAIN FUNCTION ====================
def main():
    """Main function"""
    try:
        print("Starting ADRVE Edge Device...")
        
        # Initialize YOLO model
        model = initialize_yolo()
        
        # Start YOLO detection thread
        yolo_thread = threading.Thread(target=yolo_detection_thread, args=(model,))
        yolo_thread.daemon = True
        yolo_thread.start()
        
        # Initialize IoT
        iot_client = initialize_iot()
        if iot_client:
            setup_iot_subscriptions(iot_client)
        
        # Start KVS producer
        kvs_process = start_kvs_producer()
        
        # Start video capture (this will block until exit)
        capture_video()
        
        # Cleanup
        global running
        running = False
        
        print("Shutting down...")
        if kvs_process:
            kvs_process.terminate()
        
        if iot_client:
            iot_client.disconnect()
        
        print("Shutdown complete")
    
    except KeyboardInterrupt:
        print("Interrupted by user")
        global running
        running = False
    except Exception as e:
        print(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    main()
