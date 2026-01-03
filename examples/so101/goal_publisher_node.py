"""
Example Goal Publisher Node for testing SO-101 Driver

This node publishes sample joint targets for testing the SO-101 driver
in MuJoCo simulation. Replace this with your actual motion planning,
teleoperation, or policy inference logic.

The SO-101 has 6 controllable joints:
  - shoulder_pan: Base rotation
  - shoulder_lift: Shoulder pitch
  - elbow_flex: Elbow pitch
  - wrist_flex: Wrist pitch
  - wrist_roll: Wrist roll
  - gripper: Gripper open/close (0 = closed, ~1.5 = open)
"""

import json

import pyarrow as pa
from dora import Node


def main():
    """Main entry point for goal publisher node."""
    node = Node()

    # Sample poses to cycle through (6 joints in radians)
    # Format: [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]
    poses = [
        # Home position (gripper half open)
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.5],
        # Reach forward with gripper open
        [0.0, 0.5, -0.8, 0.3, 0.0, 1.2],
        # Rotate and reach
        [0.8, 0.3, -0.5, 0.2, 0.5, 0.0],
        # Other side
        [-0.8, 0.4, -0.6, 0.2, -0.5, 1.0],
        # Look down
        [0.0, 0.8, -1.2, 0.4, 0.0, 0.5],
        # Back to home
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.5],
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
                    "duration": 1.5,  # Movement duration in seconds
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
