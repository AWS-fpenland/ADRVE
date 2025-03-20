#!/usr/bin/env python3
"""
Extract a frame from a video file
"""

import cv2
import sys

if len(sys.argv) < 3:
    print("Usage: python extract_frame.py <video_file> <output_image>")
    sys.exit(1)

video_file = sys.argv[1]
output_file = sys.argv[2]

# Open the video file
cap = cv2.VideoCapture(video_file)

# Check if the video file was opened successfully
if not cap.isOpened():
    print(f"Error: Could not open video file {video_file}")
    sys.exit(1)

# Read a frame
ret, frame = cap.read()

# Check if a frame was read successfully
if not ret:
    print(f"Error: Could not read frame from {video_file}")
    sys.exit(1)

# Save the frame as an image
cv2.imwrite(output_file, frame)
print(f"Frame extracted and saved to {output_file}")

# Release the video capture object
cap.release()
