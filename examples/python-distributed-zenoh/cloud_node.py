#!/usr/bin/env python3
"""
Distributed Cloud Aggregator using Dora
Receives sensor data from distributed nodes via Dora's Zenoh routing.
"""

import json
import time
from collections import defaultdict
from dora import Node


def _ensure_bytes(value):
    """Convert Dora event values (bytes or Arrow arrays) into raw bytes."""

    if value is None:
        return b""

    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)

    # pyarrow Scalar exposes to_pybytes for binary payloads
    to_pybytes = getattr(value, "to_pybytes", None)
    if callable(to_pybytes):
        return to_pybytes()

    # Arrow arrays (e.g., UInt8Array) provide a Python list view of integers
    to_pylist = getattr(value, "to_pylist", None)
    if callable(to_pylist):
        try:
            return bytes(to_pylist())
        except TypeError:
            pass

    # NumPy-compatible buffers support to_numpy -> tobytes chain
    to_numpy = getattr(value, "to_numpy", None)
    if callable(to_numpy):
        array = to_numpy()
        if hasattr(array, "tobytes"):
            return array.tobytes()

    raise TypeError(f"Unsupported payload type for Dora event: {type(value)!r}")

class SensorAggregator:
    def __init__(self):
        self.sensor_data = defaultdict(lambda: {"count": 0, "last_value": None, "last_update": None})
        self.total_messages = 0

    def update(self, sensor_id, data):
        """Update sensor data"""
        self.sensor_data[sensor_id]["count"] += 1
        self.sensor_data[sensor_id]["last_value"] = data
        self.sensor_data[sensor_id]["last_update"] = time.time()
        self.total_messages += 1

    def get_active_sensors(self, timeout=5):
        """Get list of sensors that have sent data recently"""
        current_time = time.time()
        active = []
        for sensor_id, info in self.sensor_data.items():
            if info["last_update"] and (current_time - info["last_update"]) < timeout:
                active.append(sensor_id)
        return active

    def print_summary(self):
        """Print summary of all sensors"""
        active_sensors = self.get_active_sensors()
        print(f"\n{'='*70}")
        print(f"Cloud Aggregator Summary - Total Messages: {self.total_messages}")
        print(f"Active Sensors: {len(active_sensors)}")
        print(f"{'='*70}")

        for sensor_id in sorted(self.sensor_data.keys()):
            info = self.sensor_data[sensor_id]
            status = "🟢 ACTIVE" if sensor_id in active_sensors else "🔴 INACTIVE"

            if info["last_value"]:
                data = info["last_value"]
                print(f"{status} | {sensor_id:15s} | {data['sensor_type']:12s} | "
                      f"{data['value']:7.2f} {data['unit']:8s} | Count: {info['count']:5d}")
            else:
                print(f"{status} | {sensor_id:15s} | No data received yet")

        print(f"{'='*70}\n")

def main():
    print("=== Cloud Aggregator Node ===")
    print("Receiving data via Dora's distributed Zenoh routing")

    # Initialize the Dora node
    # Dora automatically handles Zenoh communication for distributed nodes
    node = Node()

    print("\nCloud aggregator started! Press Ctrl+C to stop\n")

    aggregator = SensorAggregator()
    last_summary_time = time.time()
    summary_interval = 10  # Print summary every 10 seconds

    # Process events
    try:
        for event in node:
            event_type = event["type"]

            if event_type == "INPUT":
                input_id = event["id"]

                # Handle data from different sensors
                if input_id in ["temp_data", "humidity_data", "pressure_data"]:
                    # Parse sensor data
                    raw_value = event["value"]
                    try:
                        data_bytes = _ensure_bytes(raw_value)
                    except TypeError as exc:
                        print(f"Unsupported payload for {input_id}: {exc}")
                        continue
                    payload = data_bytes.decode('utf-8')
                    data = json.loads(payload)
                    sensor_id = data["sensor_id"]

                    # Update aggregator
                    aggregator.update(sensor_id, data)

                    # Print received data
                    print(f">> [{aggregator.total_messages:05d}] Received from {sensor_id}: "
                          f"{data['sensor_type']}={data['value']}{data['unit']}")

                    # Print summary periodically
                    current_time = time.time()
                    if current_time - last_summary_time >= summary_interval:
                        aggregator.print_summary()
                        last_summary_time = current_time

            elif event_type == "STOP":
                print("Received stop signal")
                break

            elif event_type == "INPUT_CLOSED":
                print(f"Input `{event['id']}` was closed")

    except KeyboardInterrupt:
        print("\n\nReceived Ctrl+C, shutting down...")

    # Print final summary
    print("\n=== Final Summary ===")
    aggregator.print_summary()

    print("Cloud aggregator exited successfully")

if __name__ == "__main__":
    main()
