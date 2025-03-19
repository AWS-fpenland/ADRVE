#!/usr/bin/env python3
"""
KVS Debug Script - Tests the connection to Kinesis Video Streams
"""

import os
import sys
import json
import boto3
import subprocess
import time

# KVS Configuration
AWS_REGION = "us-west-2"
STREAM_NAME = "adrve-video-stream"
KVS_PRODUCER_PATH = "/mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build"

def setup_aws_credentials(profile_name="default"):
    """Set up AWS credentials for the script and KVS producer"""
    print(f"Setting up AWS credentials using profile: {profile_name}")
    
    try:
        # Set environment variables for AWS SDK
        os.environ['AWS_PROFILE'] = profile_name
        
        # Create a boto3 session with the specified profile
        session = boto3.Session(profile_name=profile_name)
        credentials = session.get_credentials()
        
        if not credentials:
            print(f"No credentials found for profile: {profile_name}")
            return False
            
        # Create .kvs directory if it doesn't exist
        os.makedirs(".kvs", exist_ok=True)
        
        # Write credentials to file for KVS producer
        cred_data = {
            "accessKeyId": credentials.access_key,
            "secretAccessKey": credentials.secret_key
        }
        
        # Add session token if present (for temporary credentials)
        if credentials.token:
            cred_data["sessionToken"] = credentials.token
            
        # Write credentials to file
        with open(".kvs/credential", "w") as f:
            json.dump(cred_data, f)
            
        print("AWS credentials set up successfully")
        
        # Print credential info (without showing actual values)
        print(f"Access Key ID: {credentials.access_key[:5]}...{credentials.access_key[-4:]}")
        print(f"Secret Access Key: {credentials.secret_key[:3]}...{credentials.secret_key[-4:]}")
        if credentials.token:
            print(f"Session Token: {credentials.token[:10]}...{credentials.token[-10:]}")
        
        return True
        
    except Exception as e:
        print(f"Error setting up AWS credentials: {str(e)}")
        return False

def check_kvs_stream_exists():
    """Check if the KVS stream exists"""
    try:
        # Create KVS client
        kvs_client = boto3.client('kinesisvideo', region_name=AWS_REGION)
        
        # List streams
        response = kvs_client.list_streams()
        
        # Check if our stream exists
        stream_exists = False
        for stream in response.get('StreamInfoList', []):
            if stream['StreamName'] == STREAM_NAME:
                stream_exists = True
                print(f"Stream '{STREAM_NAME}' exists with ARN: {stream['StreamARN']}")
                print(f"Status: {stream['Status']}")
                print(f"Creation Time: {stream['CreationTime']}")
                break
        
        if not stream_exists:
            print(f"Stream '{STREAM_NAME}' does not exist. Creating it...")
            # Create the stream
            response = kvs_client.create_stream(
                StreamName=STREAM_NAME,
                DataRetentionInHours=2,
                MediaType='video/h264'
            )
            print(f"Stream created with ARN: {response['StreamARN']}")
        
        return True
    
    except Exception as e:
        print(f"Error checking KVS stream: {str(e)}")
        return False

def test_kvs_producer():
    """Test the KVS producer with a simple command"""
    try:
        # Ensure the log directory exists
        os.makedirs("log", exist_ok=True)
        
        # Set environment variables
        os.environ['KVSSINK_LOG_CONFIG_PATH'] = os.path.abspath('kvs_log_configuration')
        os.environ['KVSSINK_VERBOSE_LOGGING'] = '1'
        
        # Build command for the KVS producer
        kvs_command = [
            f"{KVS_PRODUCER_PATH}/kvs_gstreamer_sample",
            f"AWS_REGION={AWS_REGION}",
            f"STREAM_NAME={STREAM_NAME}",
            "VIDEO_WIDTH=640",
            "VIDEO_HEIGHT=480",
            "VIDEO_FPS=15",
            "RETENTION_PERIOD=2",
            f"LOG_CONFIG_PATH={os.path.abspath('kvs_log_configuration')}"
        ]
        
        # Set environment variables for the process
        env = os.environ.copy()
        env['LD_LIBRARY_PATH'] = f"{KVS_PRODUCER_PATH}:{os.environ.get('LD_LIBRARY_PATH', '')}"
        
        print(f"Executing command: {' '.join(kvs_command)}")
        
        # Start process and capture output
        process = subprocess.Popen(
            kvs_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )
        
        # Read output for a short time
        print("KVS producer output:")
        start_time = time.time()
        while time.time() - start_time < 30:  # Run for 30 seconds
            stdout_line = process.stdout.readline()
            if stdout_line:
                print(f"OUT: {stdout_line.strip()}")
            
            stderr_line = process.stderr.readline()
            if stderr_line:
                print(f"ERR: {stderr_line.strip()}")
            
            if process.poll() is not None:
                break
        
        # Terminate the process
        if process.poll() is None:
            process.terminate()
            print("KVS producer terminated")
        else:
            print(f"KVS producer exited with code: {process.returncode}")
        
        # Get any remaining output
        stdout, stderr = process.communicate()
        if stdout:
            print(f"Remaining stdout: {stdout}")
        if stderr:
            print(f"Remaining stderr: {stderr}")
        
    except Exception as e:
        print(f"Error testing KVS producer: {str(e)}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='KVS Debug Script')
    parser.add_argument('--profile', type=str, default='default',
                       help='AWS profile name to use')
    args = parser.parse_args()
    
    print("KVS Debug Script")
    print("================")
    
    # Setup AWS credentials
    if not setup_aws_credentials(args.profile):
        print("Failed to set up AWS credentials. Exiting.")
        return
    
    # Check if KVS stream exists
    if not check_kvs_stream_exists():
        print("Failed to check KVS stream. Exiting.")
        return
    
    # Test KVS producer
    test_kvs_producer()
    
    print("Debug script completed")

if __name__ == "__main__":
    main()
