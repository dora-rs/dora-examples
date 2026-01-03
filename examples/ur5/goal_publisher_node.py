"""
Example Goal Publisher Node for testing UR5 Driver

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
    # UR5 joint limits: Base(-2pi, 2pi), Shoulder(-2pi, 2pi), Elbow(-2pi, 2pi),
    #                   Wrist1(-2pi, 2pi), Wrist2(-2pi, 2pi), Wrist3(-2pi, 2pi)
    # Using safe positions within typical workspace
    poses = [
        # Home position (arm pointing up, ready pose)
        [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0],
        # Pose 1 - rotated base, slightly different configuration
        [0.5, -1.2, 1.3, -1.6708, -1.5708, 0.5],
        # Pose 2 - different configuration
        [-0.5, -1.8, 1.8, -1.5708, -1.5708, -0.5],
        # Pose 3 - back to ready variation
        [0.0, -1.3, 1.2, -1.4708, -1.5708, 0.0],
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
                    "acceleration": 0.5,
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
