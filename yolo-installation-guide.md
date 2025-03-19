# YOLOv11 Setup Guide for ADRVE

This guide will walk you through setting up YOLOv11 on your laptop for local object detection in the ADRVE system.

## Prerequisites

- Python 3.8 or higher
- CUDA-compatible GPU (recommended for real-time performance)
- OBS Studio installed
- AWS CLI configured with appropriate permissions

## Installation Steps

### 1. Create a Python Virtual Environment

```bash
# Create a new directory for your project
mkdir adrve-edge
cd adrve-edge

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 2. Install Required Packages

```bash
# Install ultralytics (which includes YOLOv11)
pip install ultralytics

# Install other required packages
pip install opencv-python boto3 AWSIoTPythonSDK
```

### 3. Download YOLOv11 Model

```python
# You can run this in Python to download the model
from ultralytics import YOLO

# This will download the YOLOv11n model if not already present
model = YOLO("yolo11n.pt")
```

### 4. Install Kinesis Video Streams Producer SDK

The Kinesis Video Streams Producer SDK is required to stream video to AWS. Follow these steps:

#### On Ubuntu/Debian:

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    libcurl4-openssl-dev \
    liblog4cplus-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-base-apps \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-tools \
    gstreamer1.0-vaapi \
    git

# Clone and build KVS C++ Producer SDK
git clone https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp.git
cd amazon-kinesis-video-streams-producer-sdk-cpp
mkdir build
cd build
cmake .. -DBUILD_GSTREAMER_PLUGIN=ON
make
```

#### On macOS:

```bash
# Install dependencies using Homebrew
brew update
brew install cmake openssl log4cplus gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly

# Clone and build KVS C++ Producer SDK
git clone https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp.git
cd amazon-kinesis-video-streams-producer-sdk-cpp
mkdir build
cd build
cmake .. -DBUILD_GSTREAMER_PLUGIN=ON
make
```

#### On Windows:

For Windows, you can use WSL (Windows Subsystem for Linux) and follow the Ubuntu/Debian instructions, or follow the detailed Windows build instructions in the [KVS C++ SDK GitHub repository](https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp).

### 5. Configure AWS IoT Certificates

1. In the AWS IoT Core console, create a thing for your edge device
2. Generate and download certificates
3. Place them in a secure directory (e.g., `~/certs/`)
4. Update the paths in the edge device script

## Integration with OBS Studio

For the POC, we'll use a simple approach where:

1. OBS Studio captures your webcam or screen
2. Our script uses OpenCV to access the same video source directly 
3. YOLO processes frames from OpenCV
4. The Kinesis Video Producer sends the video to AWS

For a production system, you might want to:
- Create an OBS plugin that integrates YOLO directly
- Use OBS's virtual camera output as the input for our script
- Consider using NVIDIA DeepStream or Intel OpenVINO for better performance

## Testing Your Setup

1. Run OBS Studio and set up your video source
2. Run the edge device script provided in the deployment package:

```bash
python edge_device.py
```

3. The script should:
   - Initialize YOLO
   - Connect to AWS IoT Core
   - Start the KVS producer
   - Begin capturing video and performing detections

## Troubleshooting

### Common Issues:

1. **CUDA/GPU issues**: If you see errors related to CUDA, make sure you have NVIDIA drivers installed and CUDA toolkit set up. As a fallback, YOLOv11 can run on CPU, but performance will be slower.

2. **Camera access conflicts**: If OBS and our script both try to access the camera directly, you might encounter issues. Use OBS Virtual Camera or try different camera indices.

3. **AWS credential errors**: Make sure your AWS CLI is configured correctly with credentials that have permission to access Kinesis Video Streams and IoT Core.

4. **KVS Producer errors**: Check if the KVS producer was built correctly and that you've set the correct path in the script.

### Performance Optimization:

- Reduce resolution or frame rate if detection is too slow
- Use YOLOv11n (nano) for better speed, or YOLOv11s (small) if you need more accuracy
- Set YOLO confidence threshold higher to reduce false positives
- Limit the classes to detect to only those relevant to your use case
