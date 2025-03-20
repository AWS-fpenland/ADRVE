#!/usr/bin/env python3
"""
Fix for MQTT publishing in edge-device-video-file.py
"""

import sys

def apply_mqtt_fix():
    # Read the original file
    with open('edge-device-video-file.py', 'r') as f:
        lines = f.readlines()
    
    # Find the mqtt_publish_thread function
    mqtt_thread_found = False
    for i, line in enumerate(lines):
        if 'def mqtt_publish_thread(client):' in line:
            mqtt_thread_found = True
            # Find the publishing section
            for j in range(i, len(lines)):
                if 'if current_time - last_mqtt_publish_time >= MQTT_PUBLISH_INTERVAL:' in lines[j]:
                    # Find the section where we get data from the queue
                    for k in range(j, j+20):  # Look in next 20 lines
                        if 'if not detection_queue.empty():' in lines[k]:
                            # This is the line we need to modify
                            indent = lines[k].split('if')[0]
                            
                            # Find the end of this block
                            block_end = k
                            for m in range(k+1, k+20):
                                if lines[m].startswith(indent + '# Update last publish time'):
                                    block_end = m
                                    break
                            
                            # Replace the block with fixed code
                            fixed_code = [
                                f"{indent}if not detection_queue.empty():\n",
                                f"{indent}    _, detection_data = detection_queue.get()\n",
                                f"{indent}    \n",
                                f"{indent}    # Publish detection to IoT Core\n",
                                f"{indent}    topic = f\"{{IOT_TOPIC_PREFIX}}/status/{{IOT_THING_NAME}}/detection\"\n",
                                f"{indent}    try:\n",
                                f"{indent}        print(f\"Publishing detection with {{len(detection_data['detections'])}} objects to MQTT\")\n",
                                f"{indent}        client.publish(topic, json.dumps(detection_data), 0)\n",
                                f"{indent}        print(f\"Successfully published to {{topic}}\")\n",
                                f"{indent}    except Exception as e:\n",
                                f"{indent}        print(f\"Error publishing to MQTT: {{e}}\")\n",
                                f"{indent}    \n",
                                f"{indent}    # Update last publish time\n",
                                f"{indent}    last_mqtt_publish_time = current_time\n",
                                f"{indent}else:\n",
                                f"{indent}    # No detections to publish\n",
                                f"{indent}    if int(current_time) % 5 == 0:  # Log every 5 seconds\n",
                                f"{indent}        print(\"No detections to publish - queue is empty\")\n"
                            ]
                            
                            # Replace the block
                            lines[k:block_end+1] = fixed_code
                            break
                    break
            break
    
    if not mqtt_thread_found:
        print("Could not find mqtt_publish_thread function")
        return
    
    # Write the modified file
    with open('edge-device-video-file-fixed.py', 'w') as f:
        f.writelines(lines)
    
    print("MQTT fix applied. New file created: edge-device-video-file-fixed.py")
    print("Run with: python edge-device-video-file-fixed.py --video-file 1test0.mkv --profile org-master")

if __name__ == "__main__":
    apply_mqtt_fix()
