"""
DORA-RS Driver Node for Lebai Robot Arm (LM3)

This node receives target joint goals and controls the Lebai robot arm.
It supports both simulation and real robot modes.

Inputs:
    - target_joints: Joint angles as JSON array [j1, j2, j3, j4, j5, j6] in radians
    - target_pose: Cartesian pose as JSON dict {"x", "y", "z", "rx", "ry", "rz"}
    - command: Control commands ("start", "stop", "home", "get_joints")

Outputs:
    - current_joints: Current joint positions
    - status: Movement status ("idle", "moving", "completed", "error")
    - error: Error messages if any
"""

import json
import os
from typing import Any

import lebai_sdk
import pyarrow as pa
from dora import Node


class LebaiDriverNode:
    """DORA driver node for Lebai robot arm control."""

    def __init__(self):
        self.arm = None
        self.ip = os.getenv("LEBAI_IP", "127.0.0.1")
        self.simulation = os.getenv("LEBAI_SIMULATION", "true").lower() == "true"
        self.acceleration = float(os.getenv("LEBAI_ACCELERATION", "0.6"))
        self.velocity = float(os.getenv("LEBAI_VELOCITY", "0.3"))
        self.connected = False

        # Home position (6-axis joint angles in radians)
        self.home_position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def connect(self) -> dict:
        """Connect to the Lebai robot."""
        try:
            lebai_sdk.init()
            self.arm = lebai_sdk.connect(self.ip, self.simulation)

            if not self.arm.is_connected():
                return {
                    "success": False,
                    "error": "Connection failed: Check docker/robot status",
                }

            self.arm.start_sys()
            self.connected = True
            return {"success": True, "message": "Connected to Lebai robot"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disconnect(self) -> dict:
        """Disconnect from the robot."""
        try:
            if self.arm and self.connected:
                self.arm.stop_sys()
                self.connected = False
            return {"success": True, "message": "Disconnected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_current_joints(self) -> dict:
        """Get current joint positions."""
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}
            joints = self.arm.get_actual_joint()
            return {"success": True, "joints": list(joints)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_joints(
        self,
        target_joints: list,
        acceleration: float = None,
        velocity: float = None,
        wait: bool = True,
    ) -> dict:
        """
        Move robot to target joint positions.

        Args:
            target_joints: List of 6 joint angles in radians
            acceleration: Joint acceleration (rad/s^2)
            velocity: Joint velocity (rad/s)
            wait: Whether to wait for movement to complete
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            if len(target_joints) != 6:
                return {"success": False, "error": "Expected 6 joint values"}

            acc = acceleration if acceleration is not None else self.acceleration
            vel = velocity if velocity is not None else self.velocity

            self.arm.movej(target_joints, a=acc, v=vel, t=0, r=0)

            if wait:
                self.arm.wait_move()

            return {"success": True, "message": "Movement completed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_linear(
        self,
        target_pose: dict,
        acceleration: float = None,
        velocity: float = None,
        wait: bool = True,
    ) -> dict:
        """
        Move robot linearly to target Cartesian pose.

        Args:
            target_pose: Dict with keys x, y, z, rx, ry, rz
            acceleration: Linear acceleration
            velocity: Linear velocity
            wait: Whether to wait for movement to complete
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            required_keys = ["x", "y", "z", "rx", "ry", "rz"]
            if not all(k in target_pose for k in required_keys):
                return {"success": False, "error": f"Expected keys: {required_keys}"}

            acc = acceleration if acceleration is not None else self.acceleration
            vel = velocity if velocity is not None else self.velocity

            pose = [
                target_pose["x"],
                target_pose["y"],
                target_pose["z"],
                target_pose["rx"],
                target_pose["ry"],
                target_pose["rz"],
            ]

            self.arm.movel(pose, a=acc, v=vel, t=0, r=0)

            if wait:
                self.arm.wait_move()

            return {"success": True, "message": "Linear movement completed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def go_home(self) -> dict:
        """Move robot to home position."""
        return self.move_joints(self.home_position)


def main():
    """Main entry point for DORA node."""
    node = Node()
    driver = LebaiDriverNode()

    # Auto-connect on startup
    connect_result = driver.connect()
    print(f"[LebaiDriver] Connection: {connect_result}")

    if not connect_result.get("success"):
        # Send error status
        node.send_output(
            "error",
            pa.array([json.dumps(connect_result)]),
        )

    # Send initial status
    node.send_output("status", pa.array(["idle"]))

    for event in node:
        event_type = event["type"]

        if event_type == "INPUT":
            event_id = event["id"]
            data = event["value"]

            try:
                # Parse input data
                if hasattr(data, "to_pylist"):
                    data_list = data.to_pylist()
                    if data_list:
                        data_str = data_list[0]
                    else:
                        continue
                else:
                    data_str = str(data)

                # Handle different input types
                if event_id == "target_joints":
                    # Send moving status
                    node.send_output("status", pa.array(["moving"]))

                    # Parse joint targets
                    if isinstance(data_str, str):
                        target = json.loads(data_str)
                    else:
                        target = data_str

                    # Extract joints array and optional parameters
                    if isinstance(target, dict):
                        joints = target.get("joints", target.get("target", []))
                        acc = target.get("acceleration")
                        vel = target.get("velocity")
                        wait = target.get("wait", True)
                    else:
                        joints = list(target)
                        acc = None
                        vel = None
                        wait = True

                    result = driver.move_joints(
                        joints, acceleration=acc, velocity=vel, wait=wait
                    )

                    if result.get("success"):
                        node.send_output("status", pa.array(["completed"]))
                        # Send current joints after movement
                        joints_result = driver.get_current_joints()
                        if joints_result.get("success"):
                            node.send_output(
                                "current_joints",
                                pa.array([json.dumps(joints_result["joints"])]),
                            )
                    else:
                        node.send_output("status", pa.array(["error"]))
                        node.send_output(
                            "error", pa.array([json.dumps(result)])
                        )

                elif event_id == "target_pose":
                    # Send moving status
                    node.send_output("status", pa.array(["moving"]))

                    # Parse pose target
                    if isinstance(data_str, str):
                        target = json.loads(data_str)
                    else:
                        target = data_str

                    result = driver.move_linear(target)

                    if result.get("success"):
                        node.send_output("status", pa.array(["completed"]))
                    else:
                        node.send_output("status", pa.array(["error"]))
                        node.send_output(
                            "error", pa.array([json.dumps(result)])
                        )

                elif event_id == "command":
                    # Handle control commands
                    if isinstance(data_str, str):
                        cmd = data_str.strip().lower()
                    else:
                        cmd = str(data_str).strip().lower()

                    if cmd == "start":
                        result = driver.connect()
                        node.send_output(
                            "status",
                            pa.array(
                                ["idle" if result.get("success") else "error"]
                            ),
                        )

                    elif cmd == "stop":
                        result = driver.disconnect()
                        node.send_output("status", pa.array(["stopped"]))

                    elif cmd == "home":
                        node.send_output("status", pa.array(["moving"]))
                        result = driver.go_home()
                        node.send_output(
                            "status",
                            pa.array(
                                [
                                    "completed"
                                    if result.get("success")
                                    else "error"
                                ]
                            ),
                        )

                    elif cmd == "get_joints":
                        result = driver.get_current_joints()
                        if result.get("success"):
                            node.send_output(
                                "current_joints",
                                pa.array([json.dumps(result["joints"])]),
                            )
                        else:
                            node.send_output(
                                "error", pa.array([json.dumps(result)])
                            )

                    else:
                        node.send_output(
                            "error",
                            pa.array([f"Unknown command: {cmd}"]),
                        )

            except json.JSONDecodeError as e:
                node.send_output(
                    "error", pa.array([f"JSON parse error: {str(e)}"])
                )
            except Exception as e:
                node.send_output("status", pa.array(["error"]))
                node.send_output("error", pa.array([str(e)]))

        elif event_type == "STOP":
            print("[LebaiDriver] Received STOP signal")
            driver.disconnect()
            break

        elif event_type == "ERROR":
            print(f"[LebaiDriver] Error: {event}")

    print("[LebaiDriver] Node shutdown complete")


if __name__ == "__main__":
    main()
