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
