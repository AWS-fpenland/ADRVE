#!/usr/bin/env python3
"""
Debug patch to be applied to edge-device-video-file.py
This adds debug prints to help troubleshoot MQTT publishing issues
"""

import sys

def apply_debug_patch():
    # Read the original file
    with open('edge-device-video-file.py', 'r') as f:
        content = f.read()
    
    # Add DEBUG_MODE flag after imports
    if 'DEBUG_MODE =' not in content:
        import_section_end = content.find('# ==================== CONFIG ====================')
        if import_section_end > 0:
            modified_content = content[:import_section_end] + '\n# Debug flag\nDEBUG_MODE = True\n\n' + content[import_section_end:]
            content = modified_content
    
    # Add debug print in mqtt_publish_thread function
    mqtt_thread_start = content.find('def mqtt_publish_thread(client):')
    if mqtt_thread_start > 0:
        mqtt_thread_end = content.find('# Brief pause to prevent CPU overuse', mqtt_thread_start)
        if mqtt_thread_end > 0:
            # Find the position to insert our debug code
            insert_pos = content.find('if current_time - last_mqtt_publish_time >= MQTT_PUBLISH_INTERVAL:', mqtt_thread_start)
            if insert_pos > 0:
                # Find the end of the if block
                next_line_pos = content.find('\n', insert_pos)
                if next_line_pos > 0:
                    debug_code = """
            # Debug: Print queue status
            if DEBUG_MODE:
                print(f"MQTT thread: Queue size = {detection_queue.qsize()}, Time since last publish: {current_time - last_mqtt_publish_time:.2f}s")
                
                # Send heartbeat every 5 seconds
                if int(current_time) % 5 == 0:
                    heartbeat_topic = f"{IOT_TOPIC_PREFIX}/status/{IOT_THING_NAME}/heartbeat"
                    heartbeat_msg = {
                        "timestamp": current_time,
                        "status": "alive",
                        "queue_size": detection_queue.qsize()
                    }
                    try:
                        client.publish(heartbeat_topic, json.dumps(heartbeat_msg), 0)
                        print(f"Published heartbeat to {heartbeat_topic}")
                    except Exception as e:
                        print(f"Error publishing heartbeat: {e}")
"""
                    modified_content = content[:next_line_pos+1] + debug_code + content[next_line_pos+1:]
                    content = modified_content
    
    # Add debug print in yolo_detection_thread function
    yolo_thread_start = content.find('def yolo_detection_thread(model):')
    if yolo_thread_start > 0:
        # Find where detections are processed
        detection_pos = content.find('detections = []', yolo_thread_start)
        if detection_pos > 0:
            # Find the end of the detection processing
            end_detection_pos = content.find('# Put results in the detection queue', detection_pos)
            if end_detection_pos > 0:
                debug_code = """
                    # Debug: Print detection results
                    if DEBUG_MODE and len(detections) > 0:
                        print(f"YOLO thread: Found {len(detections)} objects with confidence > {CONFIDENCE_THRESHOLD}")
                        for d in detections[:3]:  # Print first 3 detections
                            print(f"  {d['class']} (conf: {d['confidence']:.2f})")
                        if len(detections) > 3:
                            print(f"  ... and {len(detections) - 3} more")
"""
                modified_content = content[:end_detection_pos] + debug_code + content[end_detection_pos:]
                content = modified_content
    
    # Write the modified file
    with open('edge-device-video-file-debug.py', 'w') as f:
        f.write(content)
    
    print("Debug patch applied. New file created: edge-device-video-file-debug.py")
    print("Run with: python edge-device-video-file-debug.py --video-file 1test0.mkv --profile org-master")

if __name__ == "__main__":
    apply_debug_patch()
