#!/usr/bin/env python3
import boto3
import json

try:
    # Create IoT client
    client = boto3.client('iot', region_name='us-west-2')
    
    # List topic rules
    print("Listing IoT topic rules...")
    response = client.list_topic_rules()
    print(json.dumps(response, indent=2))
    
    # Try to get specific rule if any exist
    if response.get('rules'):
        rule_name = response['rules'][0]['ruleName']
        print(f"\nGetting details for rule: {rule_name}")
        rule_response = client.get_topic_rule(ruleName=rule_name)
        print(json.dumps(rule_response, indent=2))
    
    # Test publishing to the topic
    print("\nTesting MQTT publish...")
    iot_data = boto3.client('iot-data', region_name='us-west-2')
    test_message = {
        "timestamp": 1616161616,
        "detections": [
            {
                "box": [100, 100, 200, 200],
                "class": "person",
                "class_id": 0,
                "confidence": 0.95
            }
        ],
        "source": "edge"
    }
    
    topic = "adrve/status/adrve_edge/detection"
    print(f"Publishing to topic: {topic}")
    response = iot_data.publish(
        topic=topic,
        qos=0,
        payload=json.dumps(test_message)
    )
    print(f"Publish response: {response}")
    
except Exception as e:
    print(f"Error: {e}")
