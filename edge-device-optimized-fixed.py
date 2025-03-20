#!/usr/bin/env python3
"""
ADRVE Edge Device Script - Optimized for Smooth KVS Streaming (Fixed)
------------------------------------------------------------
This script integrates:
1. RTSP streaming to AWS Kinesis Video Streams with optimized parameters
2. YOLOv11 for local object detection
3. AWS IoT Core for sending detections and receiving commands

Requirements:
- Python 3.8+
- ultralytics package (pip install ultralytics)
- boto3 (pip install boto3)
- AWSIoTPythonSDK (pip install AWSIoTPythonSDK)
- opencv-python (pip install opencv-python)
- Amazon Kinesis Video Streams Producer SDK (requires separate installation)

Before running, configure AWS credentials and update the CONFIG section.

Usage:
  python edge-device-optimized-fixed.py [--profile PROFILE_NAME] [--no-display] [--rtsp-url URL]
  
  --profile: Optional AWS profile name to use (default: default)
  --no-display: Run without displaying video locally
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
FPS = 30  # Increased from 15 to 30 for smoother streaming
KVS_PRODUCER_PATH = "/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"

# KVS Optimization Parameters
KVS_STORAGE_SIZE = 512       # Increased from 128 to 512 MB
KVS_FRAGMENT_DURATION = 2000 # 2 seconds (in milliseconds)
KVS_MAX_LATENCY = 0          # Minimize latency

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
# Detection results queue
detection_queue = queue.Queue(maxsize=10)
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
# RTSP URL
rtsp_url = "rtsp://10.31.50.195:554/live"
# Display video locally
display_video = True

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
    global last_yolo_process_time
    
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
                    
                    # Put results in the detection queue
                    detection_result = {
                        "timestamp": timestamp,
                        "detections": detections,
                        "source": "edge"
                    }
                    
                    # Only add to queue if not full
                    if not detection_queue.full():
                        detection_queue.put((frame, detection_result))
                    
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
    global last_mqtt_publish_time
    
    if client is None:
        print("IoT client not initialized, MQTT publish thread not starting")
        return
        
    print("Starting MQTT publish thread")
    while running:
        try:
            current_time = time.time()
            
            # Only publish at the specified interval
            if current_time - last_mqtt_publish_time >= MQTT_PUBLISH_INTERVAL:
                if not detection_queue.empty():
                    _, detection_data = detection_queue.get()
                    
                    # Publish detection to IoT Core
                    topic = f"{IOT_TOPIC_PREFIX}/status/{IOT_THING_NAME}/detection"
                    client.publish(topic, json.dumps(detection_data), 0)
                    print(f"Published detection to MQTT: {len(detection_data['detections'])} objects")
                    
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
        
        # Optimized GStreamer pipeline with improved parameters
        # Removed the frame-rate parameter which was causing issues
        kvs_command = [
            "gst-launch-1.0", "-v",
            "rtspsrc", f"location={rtsp_url}", "latency=0", "buffer-mode=auto", "!",
            "rtph264depay", "!", "h264parse", "!",
            "video/x-h264,stream-format=avc,alignment=au", "!",
            "kvssink", f"stream-name={STREAM_NAME}",
            f"storage-size={KVS_STORAGE_SIZE}",
            f"max-latency={KVS_MAX_LATENCY}",
            f"fragment-duration={KVS_FRAGMENT_DURATION}",
            "key-frame-fragmentation=true",
            "nal-adaptation-flags=0x0"
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
        
        # We'll use the optimized GStreamer pipeline as our primary approach
        print(f"Using optimized GStreamer pipeline with RTSP source: {rtsp_url}")
        print(f"KVS parameters: storage-size={KVS_STORAGE_SIZE}, fragment-duration={KVS_FRAGMENT_DURATION}")
        
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
                    print(f"Method 2 failed. KVS streaming could not be started.")
                    return None
            
            return process
        except Exception as e:
            print(f"Failed to start KVS process: {str(e)}")
            return None
    except Exception as e:
        print(f"Failed to set up KVS producer: {str(e)}")
        traceback.print_exc()
        return None

def capture_video():
    """Capture video from camera and feed both to YOLO and display"""
    global running
    
    try:
        print(f"Opening video source: {rtsp_url}")
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
            sys.exit(1)
        
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
            
            # Display frame with detection overlay (if enabled)
            if display_video:
                display_frame = frame.copy()
                
                # Add detection boxes if available
                if not detection_queue.empty():
                    # Peek at the detection data without removing it
                    # This allows the MQTT thread to still get the data
                    detection_data = list(detection_queue.queue)[0][1]
                    
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
                
                # Display timestamp and FPS
                cv2.putText(display_frame, f"Time: {datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Show the frame
                cv2.imshow("ADRVE Edge Device", display_frame)
                
                # Check for exit key
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("Exit requested")
                    running = False
                    break
        
        # Clean up
        cap.release()
        if display_video:
            cv2.destroyAllWindows()
    
    except Exception as e:
        print(f"Error in video capture: {str(e)}")
        running = False

# ==================== MAIN FUNCTION ====================
def main():
    """Main function"""
    global running, rtsp_url, display_video
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ADRVE Edge Device Script - Optimized for Smooth KVS Streaming')
    parser.add_argument('--profile', type=str, default='default',
                       help='AWS profile name to use')
    parser.add_argument('--no-display', action='store_true',
                       help='Run without displaying video locally')
    parser.add_argument('--rtsp-url', type=str, default='rtsp://10.31.50.195:554/live',
                       help='RTSP URL to stream')
    args = parser.parse_args()
    
    # Set global variables from arguments
    rtsp_url = args.rtsp_url
    display_video = not args.no_display
    
    try:
        print("Starting ADRVE Edge Device - Optimized for Smooth KVS Streaming...")
        print(f"RTSP URL: {rtsp_url}")
        print(f"Local Display: {'Disabled' if not display_video else 'Enabled'}")
        
        # Setup AWS credentials
        if not setup_aws_credentials(args.profile):
            print("Failed to set up AWS credentials. Exiting.")
            return
        
        # Initialize YOLO model
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
        
        # Start YOLO detection thread
        yolo_thread = threading.Thread(target=yolo_detection_thread, args=(model,))
        yolo_thread.daemon = True
        yolo_thread.start()
        threads.append(yolo_thread)
        
        # Start MQTT publish thread (if IoT client is initialized)
        if iot_client:
            mqtt_thread = threading.Thread(target=mqtt_publish_thread, args=(iot_client,))
            mqtt_thread.daemon = True
            mqtt_thread.start()
            threads.append(mqtt_thread)
        
        # Start video capture (this will block until exit)
        capture_video()
        
        # Cleanup
        running = False
        
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
