#!/usr/bin/env python3
"""
MQTT Subscriber to monitor the ADRVE detection topic
"""

import time
import json
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# AWS IoT Configuration
IOT_ENDPOINT = "abn0shy2z8qz8-ats.iot.us-west-2.amazonaws.com"
IOT_CERT_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-certificate.pem.crt"
IOT_PRIVATE_KEY_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-private.pem.key"
IOT_ROOT_CA_PATH = "certs/AmazonRootCA1.pem"
IOT_TOPIC = "adrve/status/adrve_edge/detection"

def message_callback(client, userdata, message):
    """Callback when message is received"""
    print("\n----- New Message Received -----")
    print(f"Topic: {message.topic}")
    print(f"QoS: {message.qos}")
    
    try:
        payload = json.loads(message.payload.decode('utf-8'))
        print("Payload:")
        print(json.dumps(payload, indent=2))
        
        # Print detection summary
        if "detections" in payload:
            detections = payload["detections"]
            print(f"\nDetected {len(detections)} objects:")
            for i, det in enumerate(detections):
                print(f"  {i+1}. {det.get('class', 'unknown')} - Confidence: {det.get('confidence', 0):.2f}")
    except Exception as e:
        print(f"Error processing message: {e}")
        print(f"Raw payload: {message.payload}")

def main():
    # Initialize MQTT client
    client_id = f"adrve-monitor-{int(time.time())}"
    mqtt_client = AWSIoTMQTTClient(client_id)
    mqtt_client.configureEndpoint(IOT_ENDPOINT, 8883)
    mqtt_client.configureCredentials(IOT_ROOT_CA_PATH, IOT_PRIVATE_KEY_PATH, IOT_CERT_PATH)
    
    # Configure connection parameters
    mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
    mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite queueing
    mqtt_client.configureDrainingFrequency(2)  # 2 Hz
    mqtt_client.configureConnectDisconnectTimeout(10)
    mqtt_client.configureMQTTOperationTimeout(5)
    
    # Connect to AWS IoT
    print(f"Connecting to AWS IoT endpoint: {IOT_ENDPOINT}")
    mqtt_client.connect()
    print("Connected!")
    
    # Subscribe to topic
    print(f"Subscribing to topic: {IOT_TOPIC}")
    mqtt_client.subscribe(IOT_TOPIC, 0, message_callback)
    print("Subscribed! Waiting for messages...")
    print("Press Ctrl+C to exit")
    
    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Disconnecting...")
        mqtt_client.disconnect()
        print("Disconnected!")

if __name__ == "__main__":
    main()
