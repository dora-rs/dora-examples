"""
Example Goal Publisher Node for testing Franka Panda Driver

This node publishes sample joint targets for testing the driver.
Replace this with your actual motion planning or control logic.
"""

import json

import pyarrow as pa
from dora import Node


def main():
    """Main entry point for goal publisher node."""
    node = Node()

    # Sample poses to cycle through (7-axis joint angles in radians)
    # Franka Panda has 7 DOF
    poses = [
        # Home position
        [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785],
        # Reach forward
        [0.0, 0.0, 0.0, -1.571, 0.0, 1.571, 0.785],
        # Left side
        [0.785, -0.4, 0.0, -2.0, 0.0, 1.8, 0.5],
        # Right side
        [-0.785, -0.4, 0.0, -2.0, 0.0, 1.8, 1.0],
        # Pick-ready pose
        [0.0, -0.5, 0.0, -2.5, 0.0, 2.0, 0.785],
    ]

    # Gripper commands to cycle through
    gripper_commands = ["open", "close", "open", "close", "open"]

    current_pose_idx = 0

    for event in node:
        event_type = event["type"]

        if event_type == "INPUT":
            event_id = event["id"]

            if event_id == "tick":
                # Publish next target joints
                target = poses[current_pose_idx]
                gripper_cmd = gripper_commands[current_pose_idx]

                # Format as JSON with optional parameters
                payload = {
                    "joints": target,
                    "velocity": 0.3,
                    "wait": True,
                }

                print(f"[GoalPublisher] Publishing pose {current_pose_idx}: {target}")
                node.send_output(
                    "target_joints",
                    pa.array([json.dumps(payload)]),
                )

                # Also send gripper command
                print(f"[GoalPublisher] Gripper: {gripper_cmd}")
                node.send_output(
                    "gripper",
                    pa.array([gripper_cmd]),
                )

                # Cycle to next pose
                current_pose_idx = (current_pose_idx + 1) % len(poses)

        elif event_type == "STOP":
            print("[GoalPublisher] Received STOP signal")
            break

    print("[GoalPublisher] Node shutdown complete")


if __name__ == "__main__":
    main()
