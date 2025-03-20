#!/bin/bash

# Script to update the edge device script to use GPU acceleration
# Usage: ./update_edge_device_gpu.sh

echo "Updating edge-device-script.py to use NVIDIA GPU acceleration..."

# Create a backup of the original script
cp edge-device-script.py edge-device-script.py.bak
echo "Created backup at edge-device-script.py.bak"

# Update the script to use nvh264enc
sed -i 's/rtspsrc location="$rtsp_url" short-header=TRUE ! \\/rtspsrc location="$rtsp_url" short-header=TRUE ! \\/g' edge-device-script.py
sed -i 's/rtph264depay ! h264parse ! \\/rtph264depay ! h264parse ! \\/g' edge-device-script.py
sed -i 's/video\/x-h264,stream-format=avc,alignment=au ! \\/nvh264enc ! h264parse ! video\/x-h264,stream-format=avc,alignment=au ! \\/g' edge-device-script.py

# Update the kvs_command array in the script
sed -i 's/kvs_command = \[/kvs_command = \[/g' edge-device-script.py
sed -i 's/"gst-launch-1.0", "-v",/"gst-launch-1.0", "-v",/g' edge-device-script.py
sed -i 's/"rtspsrc", f"location={rtsp_url}", "short-header=TRUE", "!",/"rtspsrc", f"location={rtsp_url}", "short-header=TRUE", "!",/g' edge-device-script.py
sed -i 's/"rtph264depay", "!", "h264parse", "!",/"rtph264depay", "!", "h264parse", "!",/g' edge-device-script.py
sed -i 's/"video\/x-h264,stream-format=avc,alignment=au", "!",/"nvh264enc", "!", "h264parse", "!", "video\/x-h264,stream-format=avc,alignment=au", "!",/g' edge-device-script.py
sed -i 's/"kvssink", f"stream-name={STREAM_NAME}", "storage-size=128"/"kvssink", f"stream-name={STREAM_NAME}", "storage-size=128"/g' edge-device-script.py

echo "Script updated to use NVIDIA GPU acceleration (nvh264enc)"
echo "You can now run the edge device script with GPU acceleration"
