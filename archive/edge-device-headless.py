#!/usr/bin/env python3
"""
ADRVE Edge Device Script - Headless Optimized Version
----------------------------------------------------
This script integrates:
1. RTSP streaming to AWS Kinesis Video Streams
2. YOLOv11 for local object detection
3. AWS IoT Core for sending detections and receiving commands

This headless version removes the local video display to optimize performance.

Requirements:
- Python 3.8+
- ultralytics package (pip install ultralytics)
- boto3 (pip install boto3)
- AWSIoTPythonSDK (pip install AWSIoTPythonSDK)
- opencv-python (pip install opencv-python)
- Amazon Kinesis Video Streams Producer SDK (requires separate installation)

Before running, configure AWS credentials and update the CONFIG section.

Usage:
  python edge-device-headless.py [--profile PROFILE_NAME] [--no-yolo] [--rtsp-url URL]
  
  --profile: Optional AWS profile name to use (default: default)
  --no-yolo: Skip YOLO detection to further optimize performance
  --rtsp-url: RTSP URL to stream (default: rtsp://10.31.50.195:554/live)
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
import argparse
import traceback
from datetime import datetime
from ultralytics import YOLO
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# ==================== CONFIG ====================
# AWS Configuration
AWS_REGION = "us-west-2"  # Update with your region
IOT_ENDPOINT = "abn0shy2z8qz8-ats.iot.us-west-2.amazonaws.com"  # Get from AWS IoT Core console
IOT_CERT_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-certificate.pem.crt"
IOT_PRIVATE_KEY_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-private.pem.key"
IOT_ROOT_CA_PATH = "certs/AmazonRootCA1.pem"
IOT_THING_NAME = "adrve_edge"
IOT_TOPIC_PREFIX = "adrve"

# Video Configuration
STREAM_NAME = "adrve-video-stream"
VIDEO_DEVICE = 0  # Usually 0 for primary webcam
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FPS = 15
KVS_PRODUCER_PATH = "/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"

# YOLO Configuration
YOLO_MODEL_PATH = "yolo11n.pt"  # Will be downloaded if not present
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

# Performance Configuration
YOLO_PROCESSING_INTERVAL = 0.2  # Process frames every 0.2 seconds (5 FPS for YOLO)
MQTT_PUBLISH_INTERVAL = 1.0     # Publish detections every 1 second

# ==================== GLOBAL VARIABLES ====================
# Frame queue for YOLO processing
frame_queue = queue.Queue(maxsize=10)
# Detection results for MQTT publishing
latest_detection = None
# Flag to control threads
running = True
# Current commands from cloud
cloud_commands = {}
# AWS Profile to use
aws_profile = "default"
# Last time we processed a frame with YOLO
last_yolo_process_time = 0
# Last time we published to MQTT
last_mqtt_publish_time = 0
# Skip YOLO processing flag
skip_yolo = False
# RTSP URL
rtsp_url = "rtsp://10.31.50.195:554/live"

# ==================== AWS CREDENTIALS SETUP ====================
def setup_aws_credentials(profile_name):
    """Set up AWS credentials for the script and KVS producer"""
    global aws_profile
    
    print(f"Setting up AWS credentials using profile: {profile_name}")
    aws_profile = profile_name
    
    try:
        # Create a boto3 session with the specified profile
        session = boto3.Session(profile_name=profile_name)
        credentials = session.get_credentials()
        
        if not credentials:
            print(f"No credentials found for profile: {profile_name}")
            return False
            
        # Create .kvs directory if it doesn't exist
        os.makedirs(".kvs", exist_ok=True)
        kvs_cred_dir = os.path.join(KVS_PRODUCER_PATH, '.kvs')
        os.makedirs(kvs_cred_dir, exist_ok=True)
        
        # Get the frozen credentials to ensure they don't expire during our session
        frozen_credentials = credentials.get_frozen_credentials()
        
        # Write credentials to file for KVS producer
        cred_data = {
            "accessKeyId": frozen_credentials.access_key,
            "secretAccessKey": frozen_credentials.secret_key
        }
        
        # Add session token if present (for temporary credentials)
        if frozen_credentials.token:
            cred_data["sessionToken"] = frozen_credentials.token
            
        # Write credentials to file in both locations
        with open(".kvs/credential", "w") as f:
            json.dump(cred_data, f)
            
        with open(os.path.join(kvs_cred_dir, "credential"), "w") as f:
            json.dump(cred_data, f)
            
        # Also set environment variables for direct use
        os.environ['AWS_ACCESS_KEY_ID'] = frozen_credentials.access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = frozen_credentials.secret_key
        if frozen_credentials.token:
            os.environ['AWS_SESSION_TOKEN'] = frozen_credentials.token
        os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
            
        print("AWS credentials set up successfully")
        return True
        
    except Exception as e:
        print(f"Error setting up AWS credentials: {str(e)}")
        return False

# ==================== YOLO MODEL ====================
def initialize_yolo():
    """Initialize and return YOLO model"""
    if skip_yolo:
        print("YOLO detection disabled, skipping initialization")
        return None
        
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
    global latest_detection, last_yolo_process_time
    
    if skip_yolo or model is None:
        print("YOLO detection disabled, detection thread not starting")
        return
        
    print("Starting YOLO detection thread")
    while running:
        try:
            current_time = time.time()
            
            # Only process frames at the specified interval
            if current_time - last_yolo_process_time >= YOLO_PROCESSING_INTERVAL:
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
                    
                    # Update latest detection
                    latest_detection = {
                        "timestamp": timestamp,
                        "detections": detections,
                        "source": "edge"
                    }
                    
                    # Update last process time
                    last_yolo_process_time = current_time
                    
                    # Print detection summary
                    if detections:
                        print(f"Detected {len(detections)} objects: " + 
                              ", ".join([f"{d['class']} ({d['confidence']:.2f})" for d in detections[:3]]) +
                              ("..." if len(detections) > 3 else ""))
            
            # Brief pause to prevent CPU overuse
            time.sleep(0.01)
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
            timestamp = payload.get('timestamp', time.time())
            
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

def mqtt_publish_thread(client):
    """Thread to publish detections to MQTT at regular intervals"""
    global latest_detection, last_mqtt_publish_time
    
    if client is None:
        print("IoT client not initialized, MQTT publish thread not starting")
        return
        
    print("Starting MQTT publish thread")
    while running:
        try:
            current_time = time.time()
            
            # Only publish at the specified interval
            if current_time - last_mqtt_publish_time >= MQTT_PUBLISH_INTERVAL:
                if latest_detection is not None:
                    # Publish detection to IoT Core
                    topic = f"{IOT_TOPIC_PREFIX}/status/{IOT_THING_NAME}/detection"
                    client.publish(topic, json.dumps(latest_detection), 0)
                    print(f"Published detection to MQTT: {len(latest_detection['detections'])} objects")
                    
                    # Update last publish time
                    last_mqtt_publish_time = current_time
            
            # Brief pause to prevent CPU overuse
            time.sleep(0.1)
        except Exception as e:
            print(f"Error in MQTT publish thread: {str(e)}")
            time.sleep(1)  # Pause on error before retrying

# ==================== VIDEO STREAMING ====================
# Create log directory
os.makedirs("log", exist_ok=True)

# Set up logging environment variables
# Note: KVS producer expects the log config file in a specific location
# We'll create it directly in the KVS build directory
kvs_log_path = os.path.join(KVS_PRODUCER_PATH, 'kvs_log_configuration')
print(f"Setting KVS log configuration path to: {kvs_log_path}")
os.environ['KVSSINK_LOG_CONFIG_PATH'] = kvs_log_path
os.environ['KVSSINK_VERBOSE_LOGGING'] = '1'  # Enable verbose logging

def start_kvs_producer():
    """Start the Kinesis Video Stream producer as a separate process"""
    try:
        print("Starting KVS producer...")
        
        # Ensure the log directory exists
        os.makedirs("log", exist_ok=True)
        
        # Create .kvs directory directly in the KVS_PRODUCER_PATH
        kvs_cred_dir = os.path.join(KVS_PRODUCER_PATH, '.kvs')
        os.makedirs(kvs_cred_dir, exist_ok=True)
        
        # Read credentials from our local .kvs directory
        try:
            with open(".kvs/credential", "r") as src_file:
                cred_data = json.load(src_file)
                
                # Write credentials to the KVS producer directory
                with open(os.path.join(kvs_cred_dir, "credential"), "w") as dst_file:
                    json.dump(cred_data, dst_file)
                    
            print(f"Copied credentials to {kvs_cred_dir}")
        except Exception as e:
            print(f"Error copying credentials: {str(e)}")
            return None
        
        # Create log configuration directly in the KVS_PRODUCER_PATH
        kvs_log_config_path = os.path.join(KVS_PRODUCER_PATH, "kvs_log_configuration")
        try:
            with open("kvs_log_configuration", "r") as src_file:
                log_config = src_file.read()
                with open(kvs_log_config_path, "w") as dst_file:
                    dst_file.write(log_config)
            print(f"Copied log configuration to {kvs_log_config_path}")
        except FileNotFoundError:
            print("Log configuration file not found, continuing without it")
        
        # Method 1: Direct pass-through (no transcoding)
        # This is the most efficient method for RTSP streams that are already H.264 encoded
        kvs_command = [
            "gst-launch-1.0", "-v",
            "rtspsrc", f"location={rtsp_url}", "short-header=TRUE", "!",
            "rtph264depay", "!", "h264parse", "!",
            "video/x-h264,stream-format=avc,alignment=au", "!",
            "kvssink", f"stream-name={STREAM_NAME}", "storage-size=128"
        ]
        
        # Method 2: Use KVS GStreamer sample (fallback)
        kvs_sample_command = [
            f"{KVS_PRODUCER_PATH}/kvs_gstreamer_sample",
            f"{STREAM_NAME}",
            "-w", f"{FRAME_WIDTH}",
            "-h", f"{FRAME_HEIGHT}",
            "-f", f"{FPS}",
            "-rtsp", rtsp_url
        ]
        
        # Fallback to RTMP if needed
        # If both RTSP methods fail, we can try RTMP
        rtmp_url = "rtmp://10.31.50.195:1935/live/test"  # Update with your RTMP URL
        rtmp_command = [
            f"{KVS_PRODUCER_PATH}/kvs_gstreamer_sample",
            f"{STREAM_NAME}",
            "-w", f"{FRAME_WIDTH}",
            "-h", f"{FRAME_HEIGHT}",
            "-f", f"{FPS}",
            "-r", rtmp_url
        ]
        
        # We'll use Method 1 (direct pass-through) as our primary approach
        print(f"Using direct pass-through with RTSP source: {rtsp_url}")
        
        # Set environment variables for the process
        env = os.environ.copy()
        env['LD_LIBRARY_PATH'] = f"{KVS_PRODUCER_PATH}:{os.environ.get('LD_LIBRARY_PATH', '')}"
        env['AWS_DEFAULT_REGION'] = AWS_REGION
        env['GST_DEBUG'] = '2'  # Reduced debug level for better performance
        env['GST_PLUGIN_PATH'] = KVS_PRODUCER_PATH  # Set GStreamer plugin path to find kvssink
        
        # Explicitly set AWS credentials in environment variables
        session = boto3.Session(profile_name=aws_profile)
        credentials = session.get_credentials()
        if credentials:
            frozen_creds = credentials.get_frozen_credentials()
            env['AWS_ACCESS_KEY_ID'] = frozen_creds.access_key
            env['AWS_SECRET_ACCESS_KEY'] = frozen_creds.secret_key
            if frozen_creds.token:
                env['AWS_SESSION_TOKEN'] = frozen_creds.token
            print("Added AWS credentials to environment variables")
        
        print(f"Executing KVS command: {' '.join(kvs_command)}")
        print(f"With GST_PLUGIN_PATH: {env['GST_PLUGIN_PATH']}")
        print(f"With LD_LIBRARY_PATH: {env['LD_LIBRARY_PATH']}")
        
        # Start process and capture output
        try:
            process = subprocess.Popen(
                kvs_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,  # Enable text mode for easier reading
                bufsize=1,   # Line buffered
                env=env      # Pass environment variables
            )
            
            print(f"Started KVS producer with PID: {process.pid}")
            
            # Create threads to read output
            def read_output(pipe, prefix):
                try:
                    for line in iter(pipe.readline, ''):
                        # Only print important messages (errors, warnings)
                        if "ERROR" in line or "WARN" in line:
                            print(f"{prefix}: {line.strip()}")
                except Exception as e:
                    print(f"Error in {prefix} reader thread: {str(e)}")
                    
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "KVS OUT"))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "KVS ERR"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Check if process is running
            time.sleep(1)
            if process.poll() is not None:
                print(f"KVS process exited immediately with code: {process.returncode}")
                stdout, stderr = process.communicate()
                print(f"KVS stdout: {stdout}")
                print(f"KVS stderr: {stderr}")
                
                # Try Method 2 if Method 1 fails (KVS GStreamer sample)
                print("Method 1 failed. Trying Method 2 with KVS GStreamer sample...")
                process = subprocess.Popen(
                    kvs_sample_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env=env,
                    cwd=KVS_PRODUCER_PATH
                )
                
                # Set up output readers for Method 2
                stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "KVS OUT"))
                stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "KVS ERR"))
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                # Check if Method 2 is running
                time.sleep(1)
                if process.poll() is not None:
                    print(f"Method 2 failed. Trying Method 3 with RTMP...")
                    
                    # Try Method 3 (RTMP) if Method 2 fails
                    process = subprocess.Popen(
                        rtmp_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        env=env,
                        cwd=KVS_PRODUCER_PATH
                    )
                    
                    # Set up output readers for Method 3
                    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "KVS OUT"))
                    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "KVS ERR"))
                    stdout_thread.daemon = True
                    stderr_thread.daemon = True
                    stdout_thread.start()
                    stderr_thread.start()
                    
                    # Check if Method 3 is running
                    time.sleep(1)
                    if process.poll() is not None:
                        print(f"All methods failed. Last exit code: {process.returncode}")
                        return None
            
            return process
        except Exception as e:
            print(f"Failed to start KVS process: {str(e)}")
            return None
    except Exception as e:
        print(f"Failed to set up KVS producer: {str(e)}")
        traceback.print_exc()
        return None

def capture_video_thread():
    """Thread to capture video frames for YOLO processing"""
    global running
    
    if skip_yolo:
        print("YOLO detection disabled, video capture thread not starting")
        return
        
    try:
        print(f"Starting video capture thread for YOLO processing")
        # Try RTSP stream first, fall back to local camera if that fails
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            print(f"Failed to open RTSP stream at {rtsp_url}, falling back to local camera")
            cap = cv2.VideoCapture(VIDEO_DEVICE)
            
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, FPS)
        
        if not cap.isOpened():
            print("Failed to open video device")
            return
        
        print("Video capture started")
        frame_count = 0
        start_time = time.time()
        
        while running:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame")
                time.sleep(0.1)
                continue
            
            timestamp = time.time()
            frame_count += 1
            
            # Calculate and print FPS every 5 seconds
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"Video capture running at {fps:.2f} FPS")
            
            # Put frame in queue for YOLO processing
            # Only if queue is not full to prevent memory buildup
            if not frame_queue.full():
                frame_queue.put((frame.copy(), timestamp))
            else:
                # If queue is full, skip this frame
                pass
        
        # Clean up
        cap.release()
    
    except Exception as e:
        print(f"Error in video capture thread: {str(e)}")
        running = False

# ==================== MAIN FUNCTION ====================
def main():
    """Main function"""
    global running, skip_yolo, rtsp_url
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ADRVE Edge Device Script - Headless Optimized Version')
    parser.add_argument('--profile', type=str, default='default',
                       help='AWS profile name to use')
    parser.add_argument('--no-yolo', action='store_true',
                       help='Skip YOLO detection to further optimize performance')
    parser.add_argument('--rtsp-url', type=str, default='rtsp://10.31.50.195:554/live',
                       help='RTSP URL to stream')
    args = parser.parse_args()
    
    # Set global variables from arguments
    skip_yolo = args.no_yolo
    rtsp_url = args.rtsp_url
    
    try:
        print("Starting ADRVE Edge Device - Headless Optimized Version...")
        print(f"RTSP URL: {rtsp_url}")
        print(f"YOLO Detection: {'Disabled' if skip_yolo else 'Enabled'}")
        
        # Setup AWS credentials
        if not setup_aws_credentials(args.profile):
            print("Failed to set up AWS credentials. Exiting.")
            return
        
        # Initialize YOLO model (if not skipped)
        model = initialize_yolo()
        
        # Initialize IoT
        iot_client = initialize_iot()
        if iot_client:
            setup_iot_subscriptions(iot_client)
        
        # Start KVS producer
        kvs_process = start_kvs_producer()
        if kvs_process is None:
            print("Failed to start KVS producer. Exiting.")
            return
        
        # Start threads
        threads = []
        
        # Start YOLO detection thread (if not skipped)
        if not skip_yolo and model is not None:
            yolo_thread = threading.Thread(target=yolo_detection_thread, args=(model,))
            yolo_thread.daemon = True
            yolo_thread.start()
            threads.append(yolo_thread)
            
            # Start video capture thread (only needed for YOLO)
            capture_thread = threading.Thread(target=capture_video_thread)
            capture_thread.daemon = True
            capture_thread.start()
            threads.append(capture_thread)
        
        # Start MQTT publish thread (if IoT client is initialized)
        if iot_client:
            mqtt_thread = threading.Thread(target=mqtt_publish_thread, args=(iot_client,))
            mqtt_thread.daemon = True
            mqtt_thread.start()
            threads.append(mqtt_thread)
        
        print("All threads started. Press Ctrl+C to exit.")
        
        # Keep main thread alive
        try:
            while running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Interrupted by user")
            running = False
        
        # Cleanup
        print("Shutting down...")
        if kvs_process:
            kvs_process.terminate()
        
        if iot_client:
            iot_client.disconnect()
        
        # Wait for threads to finish
        for thread in threads:
            thread.join(timeout=2.0)
        
        print("Shutdown complete")
    
    except KeyboardInterrupt:
        print("Interrupted by user")
        running = False
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
