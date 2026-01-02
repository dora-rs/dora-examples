"""
Example Goal Publisher Node for testing Lebai Driver

This node publishes sample joint targets for testing the driver.
Replace this with your actual motion planning or control logic.
"""

import json

import pyarrow as pa
from dora import Node


def main():
    """Main entry point for goal publisher node."""
    node = Node()

    # Sample poses to cycle through (6-axis joint angles in radians)
    poses = [
        [0.0, -1.0, 1.0, 0.0, 1.57, 0.0],   # Pose 1
        [0.4, -0.9, 1.2, -0.2, 1.57, 0.3],  # Pose 2
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],     # Home
        [-0.3, -0.8, 0.9, 0.1, 1.2, -0.2],  # Pose 3
    ]

    current_pose_idx = 0

    for event in node:
        event_type = event["type"]

        if event_type == "INPUT":
            event_id = event["id"]

            if event_id == "tick":
                # Publish next target joints
                target = poses[current_pose_idx]

                # Format as JSON with optional parameters
                payload = {
                    "joints": target,
                    "acceleration": 0.6,
                    "velocity": 0.3,
                    "wait": True,
                }

                print(f"[GoalPublisher] Publishing pose {current_pose_idx}: {target}")
                node.send_output(
                    "target_joints",
                    pa.array([json.dumps(payload)]),
                )

                # Cycle to next pose
                current_pose_idx = (current_pose_idx + 1) % len(poses)

        elif event_type == "STOP":
            print("[GoalPublisher] Received STOP signal")
            break

    print("[GoalPublisher] Node shutdown complete")


if __name__ == "__main__":
    main()
