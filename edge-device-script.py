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

Usage:
  python edge-device-script.py [--profile PROFILE_NAME]
  
  --profile: Optional AWS profile name to use (default: default)
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

# ==================== GLOBAL VARIABLES ====================
# Frame queue for YOLO processing
frame_queue = queue.Queue(maxsize=10)
# Detection results queue
detection_queue = queue.Queue()
# Flag to control threads
running = True
# Current commands from cloud
cloud_commands = {}
# AWS Profile to use
aws_profile = "default"

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
        with open("kvs_log_configuration", "r") as src_file:
            log_config = src_file.read()
            with open(kvs_log_config_path, "w") as dst_file:
                dst_file.write(log_config)
                
        print(f"Copied log configuration to {kvs_log_config_path}")
        
        # Build command for the KVS producer
        # Try RTSP first (preferred by AWS documentation)
        rtsp_url = "rtsp://10.31.50.195:8554/test"  # Update with your RTSP URL
        kvs_command = [
            f"{KVS_PRODUCER_PATH}/kvs_gstreamer_sample",
            f"{STREAM_NAME}",
            "-w", f"{FRAME_WIDTH}",
            "-h", f"{FRAME_HEIGHT}",
            "-f", f"{FPS}",
            # Use RTSP source
            "-rtsp", rtsp_url
        ]
        
        # Fallback to RTMP if needed
        # If RTSP doesn't work, uncomment this and comment out the above
        # rtmp_url = "rtmp://10.31.50.195:1935/live/test"  # Update with your RTMP URL
        # kvs_command = [
        #     f"{KVS_PRODUCER_PATH}/kvs_gstreamer_sample",
        #     f"{STREAM_NAME}",
        #     "-w", f"{FRAME_WIDTH}",
        #     "-h", f"{FRAME_HEIGHT}",
        #     "-f", f"{FPS}",
        #     # Use RTMP source
        #     "-r", rtmp_url
        # ]
        
        # Set environment variables for the process
        env = os.environ.copy()
        env['LD_LIBRARY_PATH'] = f"{KVS_PRODUCER_PATH}:{os.environ.get('LD_LIBRARY_PATH', '')}"
        env['AWS_DEFAULT_REGION'] = AWS_REGION
        env['GST_DEBUG'] = '3'  # Add GStreamer debug level for more verbose output
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
        print(f"From directory: {KVS_PRODUCER_PATH}")
        print(f"With LD_LIBRARY_PATH: {env['LD_LIBRARY_PATH']}")
        print(f"With AWS_DEFAULT_REGION: {env['AWS_DEFAULT_REGION']}")
        
        # Start process and capture output
        try:
            process = subprocess.Popen(
                kvs_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,  # Enable text mode for easier reading
                bufsize=1,   # Line buffered
                env=env,      # Pass environment variables
                cwd=KVS_PRODUCER_PATH  # Run from KVS directory
            )
            
            print(f"Started KVS producer with PID: {process.pid}")
            
            # Create threads to read output
            def read_output(pipe, prefix):
                try:
                    for line in iter(pipe.readline, ''):
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
    """Capture video from camera and feed both to YOLO and the KVS producer"""
    global running
    try:
        print(f"Opening video device {VIDEO_DEVICE}")
        # Try RTMP stream first, fall back to local camera if that fails
        cap = cv2.VideoCapture("rtmp://10.31.50.195:1935/live/test")
        if not cap.isOpened():
            print("Failed to open RTMP stream, falling back to local camera")
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
                running = False
                break
        
        # Clean up
        cap.release()
        cv2.destroyAllWindows()
    
    except Exception as e:
        print(f"Error in video capture: {str(e)}")
        running = False

# ==================== MAIN FUNCTION ====================
def main():
    """Main function"""
    global running
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ADRVE Edge Device Script')
    parser.add_argument('--profile', type=str, default='default',
                       help='AWS profile name to use')
    args = parser.parse_args()
    
    try:
        print("Starting ADRVE Edge Device...")
        
        # Setup AWS credentials
        if not setup_aws_credentials(args.profile):
            print("Failed to set up AWS credentials. Exiting.")
            return
        
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
        running = False
        
        print("Shutting down...")
        if kvs_process:
            kvs_process.terminate()
        
        if iot_client:
            iot_client.disconnect()
        
        print("Shutdown complete")
    
    except KeyboardInterrupt:
        print("Interrupted by user")
        running = False
    except Exception as e:
        print(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    main()
