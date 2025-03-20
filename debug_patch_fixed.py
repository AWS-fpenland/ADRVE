#!/usr/bin/env python3
"""
Debug patch to be applied to edge-device-video-file.py
This adds debug prints to help troubleshoot MQTT publishing issues
"""

import sys

def apply_debug_patch():
    # Read the original file
    with open('edge-device-video-file.py', 'r') as f:
        lines = f.readlines()
    
    # Add DEBUG_MODE flag after imports
    debug_mode_added = False
    for i, line in enumerate(lines):
        if '# ==================== CONFIG ====================' in line:
            lines.insert(i, '# Debug flag\nDEBUG_MODE = True\n\n')
            debug_mode_added = True
            break
    
    if not debug_mode_added:
        print("Could not find CONFIG section to add DEBUG_MODE flag")
    
    # Add debug print in mqtt_publish_thread function
    mqtt_thread_found = False
    for i, line in enumerate(lines):
        if 'def mqtt_publish_thread(client):' in line:
            mqtt_thread_found = True
            # Find where to insert our debug code
            for j in range(i, len(lines)):
                if 'if current_time - last_mqtt_publish_time >= MQTT_PUBLISH_INTERVAL:' in lines[j]:
                    # Insert after this line with proper indentation
                    indent = lines[j].split('if')[0]  # Get the indentation
                    debug_code = [
                        f"{indent}    # Debug: Print queue status\n",
                        f"{indent}    if DEBUG_MODE:\n",
                        f"{indent}        print(f\"MQTT thread: Queue size = {{detection_queue.qsize()}}, Time since last publish: {{current_time - last_mqtt_publish_time:.2f}}s\")\n",
                        f"{indent}        \n",
                        f"{indent}        # Send heartbeat every 5 seconds\n",
                        f"{indent}        if int(current_time) % 5 == 0:\n",
                        f"{indent}            heartbeat_topic = f\"{{IOT_TOPIC_PREFIX}}/status/{{IOT_THING_NAME}}/heartbeat\"\n",
                        f"{indent}            heartbeat_msg = {{\n",
                        f"{indent}                \"timestamp\": current_time,\n",
                        f"{indent}                \"status\": \"alive\",\n",
                        f"{indent}                \"queue_size\": detection_queue.qsize()\n",
                        f"{indent}            }}\n",
                        f"{indent}            try:\n",
                        f"{indent}                client.publish(heartbeat_topic, json.dumps(heartbeat_msg), 0)\n",
                        f"{indent}                print(f\"Published heartbeat to {{heartbeat_topic}}\")\n",
                        f"{indent}            except Exception as e:\n",
                        f"{indent}                print(f\"Error publishing heartbeat: {{e}}\")\n"
                    ]
                    lines[j+1:j+1] = debug_code
                    break
            break
    
    if not mqtt_thread_found:
        print("Could not find mqtt_publish_thread function")
    
    # Add debug print in yolo_detection_thread function
    yolo_thread_found = False
    for i, line in enumerate(lines):
        if 'def yolo_detection_thread(model):' in line:
            yolo_thread_found = True
            # Find where detections are processed
            for j in range(i, len(lines)):
                if '# Put results in the detection queue' in lines[j]:
                    # Insert before this line with proper indentation
                    indent = lines[j].split('#')[0]  # Get the indentation
                    debug_code = [
                        f"{indent}# Debug: Print detection results\n",
                        f"{indent}if DEBUG_MODE and detections:\n",
                        f"{indent}    print(f\"YOLO thread: Found {{len(detections)}} objects with confidence > {{CONFIDENCE_THRESHOLD}}\")\n",
                        f"{indent}    for d in detections[:3]:  # Print first 3 detections\n",
                        f"{indent}        print(f\"  {{d['class']}} (conf: {{d['confidence']:.2f}})\")\n",
                        f"{indent}    if len(detections) > 3:\n",
                        f"{indent}        print(f\"  ... and {{len(detections) - 3}} more\")\n",
                        f"{indent}\n"
                    ]
                    lines[j:j] = debug_code
                    break
            break
    
    if not yolo_thread_found:
        print("Could not find yolo_detection_thread function")
    
    # Write the modified file
    with open('edge-device-video-file-debug.py', 'w') as f:
        f.writelines(lines)
    
    print("Debug patch applied. New file created: edge-device-video-file-debug.py")
    print("Run with: python edge-device-video-file-debug.py --video-file 1test0.mkv --profile org-master")

if __name__ == "__main__":
    apply_debug_patch()
