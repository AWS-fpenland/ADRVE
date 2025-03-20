#!/usr/bin/env python3
"""
Script to upload a test video to KVS
"""

import os
import time
import boto3
import argparse
import subprocess
import tempfile

def upload_video_to_kvs(video_file, stream_name):
    """Upload a video file to KVS using gstreamer"""
    try:
        # Get the KVS endpoint
        kvs_client = boto3.client('kinesisvideo', region_name='us-west-2')
        
        # Check if the stream exists
        try:
            kvs_client.describe_stream(StreamName=stream_name)
            print(f"Stream {stream_name} exists")
        except kvs_client.exceptions.ResourceNotFoundException:
            print(f"Stream {stream_name} does not exist, creating it...")
            kvs_client.create_stream(
                StreamName=stream_name,
                DataRetentionInHours=24,
                MediaType='video/h264'
            )
            print(f"Stream {stream_name} created")
        
        # Get the data endpoint
        response = kvs_client.get_data_endpoint(
            StreamName=stream_name,
            APIName='PUT_MEDIA'
        )
        endpoint = response['DataEndpoint']
        print(f"KVS endpoint: {endpoint}")
        
        # Get AWS credentials
        session = boto3.Session()
        credentials = session.get_credentials()
        access_key = credentials.access_key
        secret_key = credentials.secret_key
        session_token = credentials.token
        
        # Create a temporary file with AWS credentials
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(f"[default]\n")
            temp_file.write(f"aws_access_key_id = {access_key}\n")
            temp_file.write(f"aws_secret_access_key = {secret_key}\n")
            if session_token:
                temp_file.write(f"aws_session_token = {session_token}\n")
        
        # Set environment variables for gstreamer
        os.environ['AWS_SHARED_CREDENTIALS_FILE'] = temp_path
        
        # Build the gstreamer command
        gst_cmd = [
            'gst-launch-1.0',
            '-v',
            'filesrc', f'location={video_file}', '!',
            'decodebin', '!',
            'videoconvert', '!',
            'video/x-raw,format=I420,width=1280,height=720,framerate=30/1', '!',
            'x264enc', 'bframes=0', 'key-int-max=45', 'bitrate=500', '!',
            'video/x-h264,stream-format=avc,alignment=au,profile=baseline', '!',
            'kvssink', f'stream-name={stream_name}', 'storage-size=512', 
            f'aws-region=us-west-2'
        ]
        
        # Execute the gstreamer command
        print("Uploading video to KVS...")
        print(f"Command: {' '.join(gst_cmd)}")
        
        process = subprocess.Popen(gst_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        # Clean up the temporary credentials file
        os.unlink(temp_path)
        
        if process.returncode != 0:
            print(f"Error uploading video: {stderr.decode()}")
            return False
        
        print("Video uploaded successfully")
        return True
        
    except Exception as e:
        print(f"Error uploading video to KVS: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Upload a video file to KVS')
    parser.add_argument('--video', required=True, help='Path to the video file')
    parser.add_argument('--stream', default='adrve-video-stream', help='KVS stream name')
    args = parser.parse_args()
    
    # Check if the video file exists
    if not os.path.isfile(args.video):
        print(f"Error: Video file {args.video} not found")
        return
    
    # Upload the video to KVS
    upload_video_to_kvs(args.video, args.stream)

if __name__ == "__main__":
    main()
