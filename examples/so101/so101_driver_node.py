"""
DORA-RS Driver Node for SO-101 Follower Arm (LeRobot)

This node receives target joint goals and controls the SO-101 robot arm
using MuJoCo simulation with the official SO-ARM100 model from:
https://github.com/TheRobotStudio/SO-ARM100

The SO-101 is a 6-DOF low-cost arm commonly used in the LeRobot
teleoperation project.

Inputs:
    - target_joints: Joint angles as JSON array [shoulder_pan, shoulder_lift,
                     elbow_flex, wrist_flex, wrist_roll, gripper] in radians
    - command: Control commands ("start", "stop", "home", "get_joints")

Outputs:
    - current_joints: Current joint positions
    - status: Movement status ("idle", "moving", "completed", "error")
    - error: Error messages if any
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import cv2
import mujoco
import numpy as np
import pyarrow as pa
from dora import Node


class SO101DriverNode:
    """DORA driver node for SO-101 robot arm control using MuJoCo."""

    def __init__(self):
        self.model: Optional[mujoco.MjModel] = None
        self.data: Optional[mujoco.MjData] = None
        self.renderer: Optional[mujoco.Renderer] = None
        self.camera: Optional[mujoco.MjvCamera] = None

        # Configuration from environment
        self.show_viewer = os.getenv("SO101_SHOW_VIEWER", "true").lower() == "true"
        self.sim_timestep = float(os.getenv("SO101_TIMESTEP", "0.002"))
        self.control_freq = float(os.getenv("SO101_CONTROL_FREQ", "50"))  # Hz
        self.render_width = int(os.getenv("SO101_RENDER_WIDTH", "640"))
        self.render_height = int(os.getenv("SO101_RENDER_HEIGHT", "480"))

        # Model path (relative to this file)
        self.model_dir = Path(__file__).parent
        self.model_file = self.model_dir / "so101_new_calib.xml"

        self.connected = False
        self.num_joints = 6  # 6 actuated joints

        # Home position (6-axis joint angles in radians)
        self.home_position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.5]

        # Joint names matching the MJCF model
        self.joint_names = [
            "shoulder_pan",
            "shoulder_lift",
            "elbow_flex",
            "wrist_flex",
            "wrist_roll",
            "gripper",
        ]

        # Actuator names matching the MJCF model
        self.actuator_names = self.joint_names

    def connect(self) -> dict:
        """Initialize MuJoCo simulation."""
        try:
            # Check if model file exists
            if not self.model_file.exists():
                return {
                    "success": False,
                    "error": f"Model file not found: {self.model_file}",
                }

            # Load model from XML file
            self.model = mujoco.MjModel.from_xml_path(str(self.model_file))
            self.data = mujoco.MjData(self.model)

            # Set simulation timestep
            self.model.opt.timestep = self.sim_timestep

            # Initialize offscreen renderer for OpenCV display
            if self.show_viewer:
                try:
                    self.renderer = mujoco.Renderer(
                        self.model, self.render_height, self.render_width
                    )
                    # Create camera
                    self.camera = mujoco.MjvCamera()
                    self.camera.azimuth = 135
                    self.camera.elevation = -25
                    self.camera.distance = 0.5
                    self.camera.lookat[:] = [0.0, 0.0, 0.15]

                    # Create OpenCV window
                    cv2.namedWindow("SO-101 Simulation", cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(
                        "SO-101 Simulation", self.render_width, self.render_height
                    )
                    print("[SO101Driver] OpenCV viewer initialized")
                except Exception as e:
                    print(f"[SO101Driver] Renderer init failed: {e}")
                    self.renderer = None

            self.connected = True
            return {"success": True, "message": "MuJoCo simulation initialized"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disconnect(self) -> dict:
        """Close MuJoCo simulation."""
        try:
            if self.renderer:
                self.renderer = None
            if self.show_viewer:
                cv2.destroyAllWindows()
            self.model = None
            self.data = None
            self.connected = False
            return {"success": True, "message": "Simulation closed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def render_frame(self):
        """Render current frame to OpenCV window."""
        if self.renderer is None or not self.show_viewer:
            return

        try:
            # Update scene with camera
            self.renderer.update_scene(self.data, self.camera)

            # Render
            pixels = self.renderer.render()

            # Convert RGB to BGR for OpenCV
            frame = cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)

            # Add joint info overlay
            joints = self.get_current_joints()
            if joints.get("success"):
                joint_text = (
                    f"Joints: [{', '.join([f'{j:.2f}' for j in joints['joints']])}]"
                )
                cv2.putText(
                    frame,
                    joint_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )

            # Display
            cv2.imshow("SO-101 Simulation", frame)
            cv2.waitKey(1)  # Required for window update
        except Exception as e:
            print(f"[SO101Driver] Render error: {e}")

    def get_current_joints(self) -> dict:
        """Get current joint positions."""
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            joints = []
            for name in self.joint_names:
                joint_id = mujoco.mj_name2id(
                    self.model, mujoco.mjtObj.mjOBJ_JOINT, name
                )
                if joint_id == -1:
                    return {"success": False, "error": f"Joint not found: {name}"}
                qpos_addr = self.model.jnt_qposadr[joint_id]
                joints.append(float(self.data.qpos[qpos_addr]))

            return {"success": True, "joints": joints}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_joints(
        self,
        target_joints: list,
        duration: float = 1.0,
    ) -> dict:
        """
        Move robot to target joint positions with smooth interpolation.

        Args:
            target_joints: List of 6 joint values
            duration: Time to complete movement in seconds
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            if len(target_joints) != self.num_joints:
                return {
                    "success": False,
                    "error": f"Expected {self.num_joints} joint values",
                }

            # Get current joint positions
            current = self.get_current_joints()
            if not current.get("success"):
                return current

            start_joints = np.array(current["joints"])
            target = np.array(target_joints)

            # Simulation parameters
            steps = int(duration * self.control_freq)
            step_time = 1.0 / self.control_freq

            for i in range(steps):
                # Quintic interpolation for smooth motion
                t = (i + 1) / steps
                s = 10 * t**3 - 15 * t**4 + 6 * t**5  # Quintic ease

                # Interpolate joint positions
                interp_joints = start_joints + s * (target - start_joints)

                # Set control targets (actuator order matches joint order)
                self.data.ctrl[:] = interp_joints

                # Step simulation
                sim_steps = int(step_time / self.sim_timestep)
                for _ in range(sim_steps):
                    mujoco.mj_step(self.model, self.data)

                # Render frame
                self.render_frame()

                time.sleep(step_time * 0.3)  # Slow down for visualization

            return {"success": True, "message": "Movement completed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def go_home(self) -> dict:
        """Move robot to home position."""
        return self.move_joints(self.home_position, duration=1.5)

    def step_simulation(self, steps: int = 1):
        """Advance simulation by specified steps."""
        if self.connected:
            for _ in range(steps):
                mujoco.mj_step(self.model, self.data)
            self.render_frame()


def main():
    """Main entry point for DORA node."""
    node = Node()
    driver = SO101DriverNode()

    # Auto-connect on startup
    connect_result = driver.connect()
    print(f"[SO101Driver] Connection: {connect_result}")

    if not connect_result.get("success"):
        node.send_output(
            "error",
            pa.array([json.dumps(connect_result)]),
        )

    # Send initial status
    node.send_output("status", pa.array(["idle"]))

    # Initial render
    driver.render_frame()

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
                        duration = target.get("duration", 1.0)
                    else:
                        joints = list(target)
                        duration = 1.0

                    result = driver.move_joints(joints, duration=duration)

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
                        node.send_output("error", pa.array([json.dumps(result)]))

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
                            pa.array(["idle" if result.get("success") else "error"]),
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
                                ["completed" if result.get("success") else "error"]
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
                            node.send_output("error", pa.array([json.dumps(result)]))

                    else:
                        node.send_output(
                            "error",
                            pa.array([f"Unknown command: {cmd}"]),
                        )

            except json.JSONDecodeError as e:
                node.send_output("error", pa.array([f"JSON parse error: {str(e)}"]))
            except Exception as e:
                node.send_output("status", pa.array(["error"]))
                node.send_output("error", pa.array([str(e)]))

        elif event_type == "STOP":
            print("[SO101Driver] Received STOP signal")
            driver.disconnect()
            break

        elif event_type == "ERROR":
            print(f"[SO101Driver] Error: {event}")

    print("[SO101Driver] Node shutdown complete")


if __name__ == "__main__":
    main()
