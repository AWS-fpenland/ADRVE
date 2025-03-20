#!/usr/bin/env python3
"""
Debug script to test MQTT connectivity for ADRVE
"""

import time
import json
import os
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# AWS IoT Configuration
IOT_ENDPOINT = "abn0shy2z8qz8-ats.iot.us-west-2.amazonaws.com"
IOT_CERT_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-certificate.pem.crt"
IOT_PRIVATE_KEY_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-private.pem.key"
IOT_ROOT_CA_PATH = "certs/AmazonRootCA1.pem"
IOT_THING_NAME = "adrve_edge"
IOT_TOPIC_PREFIX = "adrve"

def main():
    # Initialize MQTT client
    client_id = f"adrve-debug-{int(time.time())}"
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
    
    # Publish test messages
    topic = f"{IOT_TOPIC_PREFIX}/status/{IOT_THING_NAME}/detection"
    
    # Test message with detection data
    test_message = {
        "timestamp": time.time(),
        "detections": [
            {
                "box": [100, 100, 200, 200],
                "class": "person",
                "class_id": 0,
                "confidence": 0.95
            }
        ],
        "source": "edge_debug"
    }
    
    print(f"Publishing test detection to topic: {topic}")
    mqtt_client.publish(topic, json.dumps(test_message), 0)
    print("Published test detection!")
    
    # Disconnect
    time.sleep(1)
    mqtt_client.disconnect()
    print("Disconnected!")

if __name__ == "__main__":
    main()
