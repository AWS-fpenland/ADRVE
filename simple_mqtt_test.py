#!/usr/bin/env python3
"""
Simple MQTT test for ADRVE
"""

import time
import json
import threading
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# AWS IoT Configuration
IOT_ENDPOINT = "abn0shy2z8qz8-ats.iot.us-west-2.amazonaws.com"
IOT_CERT_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-certificate.pem.crt"
IOT_PRIVATE_KEY_PATH = "certs/d3dd5153eda018b5702d415d3d1bd4876960ae74e7da7b92babbe40abac8ceb9-private.pem.key"
IOT_ROOT_CA_PATH = "certs/AmazonRootCA1.pem"
IOT_THING_NAME = "adrve_edge"
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
    except Exception as e:
        print(f"Error processing message: {e}")
        print(f"Raw payload: {message.payload}")

def subscribe_thread():
    """Thread to subscribe to MQTT messages"""
    # Initialize MQTT client for subscribing
    client_id = f"adrve-subscriber-{int(time.time())}"
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
    print(f"Subscriber: Connecting to AWS IoT endpoint: {IOT_ENDPOINT}")
    mqtt_client.connect()
    print("Subscriber: Connected!")
    
    # Subscribe to topic
    print(f"Subscriber: Subscribing to topic: {IOT_TOPIC}")
    mqtt_client.subscribe(IOT_TOPIC, 0, message_callback)
    print("Subscriber: Subscribed! Waiting for messages...")
    
    # Keep the thread running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Subscriber: Disconnecting...")
        mqtt_client.disconnect()
        print("Subscriber: Disconnected!")

def publish_thread():
    """Thread to publish MQTT messages"""
    # Initialize MQTT client for publishing
    client_id = f"adrve-publisher-{int(time.time())}"
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
    print(f"Publisher: Connecting to AWS IoT endpoint: {IOT_ENDPOINT}")
    mqtt_client.connect()
    print("Publisher: Connected!")
    
    # Publish messages every 2 seconds
    try:
        count = 0
        while count < 5:  # Send 5 messages
            count += 1
            timestamp = time.time()
            
            # Create test message
            test_message = {
                "timestamp": timestamp,
                "detections": [
                    {
                        "box": [100, 100, 200, 200],
                        "class": "person",
                        "class_id": 0,
                        "confidence": 0.95
                    },
                    {
                        "box": [300, 300, 400, 400],
                        "class": "car",
                        "class_id": 2,
                        "confidence": 0.85
                    }
                ],
                "source": "test_publisher",
                "count": count
            }
            
            # Publish message
            print(f"Publisher: Publishing message {count} to topic: {IOT_TOPIC}")
            mqtt_client.publish(IOT_TOPIC, json.dumps(test_message), 0)
            print(f"Publisher: Published message {count}!")
            
            # Wait before sending next message
            time.sleep(2)
        
        # Disconnect after sending all messages
        print("Publisher: Disconnecting...")
        mqtt_client.disconnect()
        print("Publisher: Disconnected!")
    except Exception as e:
        print(f"Publisher error: {e}")

def main():
    # Start subscriber thread
    sub_thread = threading.Thread(target=subscribe_thread)
    sub_thread.daemon = True
    sub_thread.start()
    
    # Wait a moment for subscriber to connect
    time.sleep(2)
    
    # Start publisher thread
    pub_thread = threading.Thread(target=publish_thread)
    pub_thread.daemon = True
    pub_thread.start()
    
    # Wait for publisher to finish
    pub_thread.join()
    
    # Keep main thread running for a bit to receive all messages
    print("Waiting for final messages...")
    time.sleep(3)
    print("Test complete!")

if __name__ == "__main__":
    main()
