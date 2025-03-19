#!/bin/bash

# Debug script for the edge device
# This script runs the edge device script with additional debugging

# Set up environment
cd /mnt/c/code/ADRVE/ADRVE

# Activate the virtual environment
source venv/bin/activate

# Set environment variables for debugging
export DEBUG_KVS=1
export DEBUG_MQTT=1
export DEBUG_CAMERA=1

# Run the edge device script with verbose output
python edge-device-script.py 2>&1 | tee edge_device_debug.log
