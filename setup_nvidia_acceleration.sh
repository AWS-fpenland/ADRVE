#!/bin/bash

# Script to set up NVIDIA GPU acceleration for GStreamer and KVS
# This script installs the necessary packages for GPU acceleration

echo "Setting up NVIDIA GPU acceleration for GStreamer and KVS..."

# Update package lists
echo "Updating package lists..."
sudo apt update

# Install NVIDIA runtime components
echo "Installing NVIDIA runtime components..."
sudo apt install -y nvidia-cuda-toolkit nvidia-cuda-dev

# Install GStreamer NVIDIA plugins
echo "Installing GStreamer NVIDIA plugins..."
sudo apt install -y \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    gstreamer1.0-x \
    gstreamer1.0-alsa \
    gstreamer1.0-gl \
    gstreamer1.0-vaapi

# Install NVIDIA specific GStreamer plugins
echo "Installing NVIDIA specific GStreamer plugins..."
sudo apt install -y nvidia-container-toolkit

# Check if we need to install the NVIDIA GStreamer plugins from the NVIDIA repository
if ! apt list --installed | grep -q "gstreamer1.0-nvvideo4linux2"; then
    echo "Adding NVIDIA repository for GStreamer plugins..."
    
    # Add NVIDIA repository key
    wget -qO - https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/3bf863cc.pub | sudo apt-key add -
    
    # Add NVIDIA repository
    sudo add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/ /"
    
    # Update package lists again
    sudo apt update
    
    # Install NVIDIA GStreamer plugins
    sudo apt install -y gstreamer1.0-nvvideo4linux2 libnvidia-encode1
fi

# Verify installation
echo "Verifying installation..."
nvidia-smi
gst-inspect-1.0 | grep -i nvidia

echo "Creating a test script to verify GPU acceleration..."
cat > test_gpu_acceleration.sh << 'EOF'
#!/bin/bash

# Test script to verify GPU acceleration with GStreamer

echo "Testing GPU acceleration with GStreamer..."

# Test NVIDIA hardware encoding
echo "Testing NVIDIA hardware encoding..."
gst-launch-1.0 -v videotestsrc num-buffers=100 ! \
    video/x-raw,width=1280,height=720 ! \
    nvh264enc ! \
    fakesink

# If the above command fails, try with nvenc
if [ $? -ne 0 ]; then
    echo "nvh264enc not available, trying with nvenc..."
    gst-launch-1.0 -v videotestsrc num-buffers=100 ! \
        video/x-raw,width=1280,height=720 ! \
        nvenc ! \
        fakesink
fi

# If both fail, try with vaapi
if [ $? -ne 0 ]; then
    echo "NVIDIA encoders not available, trying with vaapi..."
    gst-launch-1.0 -v videotestsrc num-buffers=100 ! \
        video/x-raw,width=1280,height=720 ! \
        vaapih264enc ! \
        fakesink
fi

# Test with x264enc as fallback
if [ $? -ne 0 ]; then
    echo "Hardware encoding not available, falling back to software encoding..."
    gst-launch-1.0 -v videotestsrc num-buffers=100 ! \
        video/x-raw,width=1280,height=720 ! \
        x264enc ! \
        fakesink
fi

echo "Test complete."
EOF

chmod +x test_gpu_acceleration.sh

echo "Setup complete. You can run ./test_gpu_acceleration.sh to verify GPU acceleration."
echo "To use GPU acceleration with your RTSP to KVS script, update the GStreamer pipeline to use nvh264enc or nvenc."
