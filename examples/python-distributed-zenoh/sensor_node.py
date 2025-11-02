#!/usr/bin/env python3
"""
Distributed Sensor Node using Dora
Publishes sensor data that will be routed via Dora's Zenoh integration.
"""

import json
import random
import sys
from dora import Node

def generate_sensor_data(sensor_id, sensor_type):
    """Generate simulated sensor data"""
    if sensor_type == "temperature":
        value = round(random.uniform(15.0, 35.0), 2)
        unit = "celsius"
    elif sensor_type == "humidity":
        value = round(random.uniform(30.0, 90.0), 2)
        unit = "percent"
    elif sensor_type == "pressure":
        value = round(random.uniform(980.0, 1050.0), 2)
        unit = "hPa"
    else:
        value = round(random.uniform(0.0, 100.0), 2)
        unit = "units"

    return {
        "sensor_id": sensor_id,
        "sensor_type": sensor_type,
        "value": value,
        "unit": unit
    }

def main():
    # Get configuration from command-line arguments
    if len(sys.argv) < 3:
        print("Usage: sensor_node.py <sensor_id> <sensor_type>")
        print("Example: sensor_node.py sensor_1 temperature")
        sys.exit(1)

    sensor_id = sys.argv[1]
    sensor_type = sys.argv[2]

    print(f"=== Sensor Node: {sensor_id} ===")
    print(f"Type: {sensor_type}")

    # Initialize the Dora node
    # Dora handles all Zenoh communication automatically
    node = Node()

    print(f"Sensor node {sensor_id} started!")
    print("Data will be automatically routed via Dora's Zenoh integration")
    print("Press Ctrl+C to stop\n")

    message_count = 0

    # Process Dora events
    try:
        for event in node:
            event_type = event["type"]

            if event_type == "INPUT":
                input_id = event["id"]

                if input_id == "tick":
                    # Generate sensor data
                    message_count += 1
                    data = generate_sensor_data(sensor_id, sensor_type)

                    # Serialize to JSON bytes
                    payload = json.dumps(data).encode('utf-8')

                    # Send via Dora - it will automatically route via Zenoh if needed
                    node.send_output("data", payload)
                    print(f"[{message_count:04d}] Sent: {sensor_type}={data['value']}{data['unit']}")

            elif event_type == "STOP":
                print("Received stop signal")
                break

            elif event_type == "INPUT_CLOSED":
                print(f"Input `{event['id']}` was closed")

    except KeyboardInterrupt:
        print("\n\nReceived Ctrl+C, shutting down...")

    print(f"Sensor node {sensor_id} exited successfully")

if __name__ == "__main__":
    main()
