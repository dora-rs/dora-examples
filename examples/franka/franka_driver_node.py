"""
DORA-RS Driver Node for Franka Panda Robot Arm

This node receives target joint goals and controls the Franka Panda robot arm.
Uses PyBullet for simulation with the built-in Franka Panda URDF.
Features smooth trajectory interpolation for fluid movements.

Inputs:
    - target_joints: Joint angles as JSON array [j1, j2, j3, j4, j5, j6, j7] in radians
    - target_pose: Cartesian pose as JSON dict {"x", "y", "z", "rx", "ry", "rz"}
    - command: Control commands ("start", "stop", "home", "get_joints", "get_pose")
    - gripper: Gripper commands ("open", "close", or float 0.0-0.04)

Outputs:
    - current_joints: Current joint positions
    - current_pose: Current end-effector pose
    - status: Movement status ("idle", "moving", "completed", "error")
    - error: Error messages if any
"""

import json
import math
import os
import time
from typing import Any, Optional, List

import numpy as np
import pybullet as p
import pybullet_data
import pyarrow as pa
from dora import Node


class TrajectoryGenerator:
    """Generates smooth trajectories using quintic polynomial interpolation."""

    @staticmethod
    def quintic_trajectory(
        q0: np.ndarray,
        qf: np.ndarray,
        v0: np.ndarray,
        vf: np.ndarray,
        duration: float,
        dt: float,
    ) -> tuple:
        """
        Generate quintic polynomial trajectory for smooth motion.

        Args:
            q0: Initial positions
            qf: Final positions
            v0: Initial velocities
            vf: Final velocities
            duration: Total trajectory duration
            dt: Time step

        Returns:
            Tuple of (positions, velocities, accelerations) arrays
        """
        num_steps = int(duration / dt) + 1
        t = np.linspace(0, duration, num_steps)

        # Quintic polynomial coefficients
        # q(t) = a0 + a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5
        T = duration
        T2 = T * T
        T3 = T2 * T
        T4 = T3 * T
        T5 = T4 * T

        a0 = q0
        a1 = v0
        a2 = np.zeros_like(q0)  # Zero initial acceleration
        a3 = (20 * (qf - q0) - (8 * vf + 12 * v0) * T) / (2 * T3)
        a4 = (30 * (q0 - qf) + (14 * vf + 16 * v0) * T) / (2 * T4)
        a5 = (12 * (qf - q0) - 6 * (vf + v0) * T) / (2 * T5)

        positions = []
        velocities = []
        accelerations = []

        for ti in t:
            ti2 = ti * ti
            ti3 = ti2 * ti
            ti4 = ti3 * ti
            ti5 = ti4 * ti

            pos = a0 + a1 * ti + a2 * ti2 + a3 * ti3 + a4 * ti4 + a5 * ti5
            vel = a1 + 2 * a2 * ti + 3 * a3 * ti2 + 4 * a4 * ti3 + 5 * a5 * ti4
            acc = 2 * a2 + 6 * a3 * ti + 12 * a4 * ti2 + 20 * a5 * ti3

            positions.append(pos)
            velocities.append(vel)
            accelerations.append(acc)

        return np.array(positions), np.array(velocities), np.array(accelerations)

    @staticmethod
    def compute_duration(
        q0: np.ndarray,
        qf: np.ndarray,
        max_velocity: float,
        max_acceleration: float,
    ) -> float:
        """
        Compute trajectory duration based on max velocity and acceleration.

        Args:
            q0: Initial positions
            qf: Final positions
            max_velocity: Maximum allowed velocity
            max_acceleration: Maximum allowed acceleration

        Returns:
            Recommended duration for smooth motion
        """
        delta = np.abs(qf - q0)
        max_delta = np.max(delta)

        # Time based on velocity limit
        t_vel = max_delta / max_velocity

        # Time based on acceleration limit (for quintic, peak accel ~ 5.77 * delta / T^2)
        t_acc = np.sqrt(5.77 * max_delta / max_acceleration)

        # Use the larger of the two, with minimum duration
        duration = max(t_vel, t_acc, 0.5)

        return duration


class FrankaDriverNode:
    """DORA driver node for Franka Panda robot arm control using PyBullet."""

    # Franka Panda joint limits (radians)
    JOINT_LIMITS_LOWER = [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973]
    JOINT_LIMITS_UPPER = [2.8973, 1.7628, 2.8973, -0.0698, 2.8973, 3.7525, 2.8973]

    # Franka Panda max velocities per joint (rad/s)
    MAX_JOINT_VELOCITIES = [2.175, 2.175, 2.175, 2.175, 2.61, 2.61, 2.61]

    # Franka Panda has 7 DOF + 2 finger joints
    NUM_JOINTS = 7
    FINGER_JOINTS = [9, 10]  # Left and right finger joint indices
    END_EFFECTOR_LINK = 11  # Panda hand link index

    def __init__(self):
        self.physics_client = None
        self.robot_id = None
        self.simulation = os.getenv("FRANKA_SIMULATION", "true").lower() == "true"
        self.gui = os.getenv("FRANKA_GUI", "false").lower() == "true"
        self.time_step = float(os.getenv("FRANKA_TIME_STEP", "0.001"))
        self.max_velocity = float(os.getenv("FRANKA_MAX_VELOCITY", "1.0"))
        self.max_acceleration = float(os.getenv("FRANKA_MAX_ACCELERATION", "2.0"))
        self.max_force = float(os.getenv("FRANKA_MAX_FORCE", "240.0"))
        self.connected = False

        # Home position (7 joint angles in radians - neutral pose)
        self.home_position = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]

        # Joint indices for the arm (excluding fingers)
        self.arm_joint_indices = list(range(7))

        # Current velocities for smooth transitions
        self.current_velocities = np.zeros(self.NUM_JOINTS)

        # Trajectory generator
        self.traj_gen = TrajectoryGenerator()

        # PD gains tuned for smooth motion
        self.kp = 100.0  # Position gain
        self.kd = 20.0   # Velocity gain

    def connect(self) -> dict:
        """Connect to PyBullet simulation."""
        try:
            if self.connected:
                return {"success": True, "message": "Already connected"}

            # Start PyBullet
            if self.gui:
                self.physics_client = p.connect(p.GUI)
                p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
                p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
                p.resetDebugVisualizerCamera(
                    cameraDistance=1.5,
                    cameraYaw=45,
                    cameraPitch=-30,
                    cameraTargetPosition=[0, 0, 0.5],
                )
            else:
                self.physics_client = p.connect(p.DIRECT)

            # Set up simulation
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
            p.setGravity(0, 0, -9.81)
            p.setTimeStep(self.time_step)

            # Enable real-time simulation for smoother motion in GUI mode
            if self.gui:
                p.setRealTimeSimulation(0)  # We'll control stepping manually

            # Load ground plane
            p.loadURDF("plane.urdf")

            # Load Franka Panda robot
            self.robot_id = p.loadURDF(
                "franka_panda/panda.urdf",
                basePosition=[0, 0, 0],
                useFixedBase=True,
            )

            # Get joint info
            num_joints = p.getNumJoints(self.robot_id)
            print(f"[FrankaDriver] Loaded robot with {num_joints} joints")

            # Disable default velocity motors for torque control
            for i in self.arm_joint_indices:
                p.setJointMotorControl2(
                    self.robot_id,
                    i,
                    p.VELOCITY_CONTROL,
                    force=0,
                )

            # Set initial position to home
            for i, joint_pos in enumerate(self.home_position):
                p.resetJointState(self.robot_id, i, joint_pos, 0)

            # Open gripper initially
            for finger_joint in self.FINGER_JOINTS:
                p.resetJointState(self.robot_id, finger_joint, 0.04, 0)

            self.current_velocities = np.zeros(self.NUM_JOINTS)
            self.connected = True

            return {
                "success": True,
                "message": f"Connected to PyBullet simulation (GUI: {self.gui})",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def disconnect(self) -> dict:
        """Disconnect from simulation."""
        try:
            if self.physics_client is not None:
                p.disconnect(self.physics_client)
                self.physics_client = None
                self.robot_id = None
                self.connected = False
            return {"success": True, "message": "Disconnected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_current_joints(self) -> dict:
        """Get current joint positions and velocities."""
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            joint_positions = []
            joint_velocities = []
            for i in self.arm_joint_indices:
                state = p.getJointState(self.robot_id, i)
                joint_positions.append(state[0])  # Position
                joint_velocities.append(state[1])  # Velocity

            return {
                "success": True,
                "joints": joint_positions,
                "velocities": joint_velocities,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_current_pose(self) -> dict:
        """Get current end-effector pose."""
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            # Get link state for end effector
            link_state = p.getLinkState(self.robot_id, self.END_EFFECTOR_LINK)
            position = link_state[0]
            orientation = link_state[1]

            # Convert quaternion to euler angles
            euler = p.getEulerFromQuaternion(orientation)

            pose = {
                "x": position[0],
                "y": position[1],
                "z": position[2],
                "rx": euler[0],
                "ry": euler[1],
                "rz": euler[2],
            }

            return {"success": True, "pose": pose}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_joints_smooth(
        self,
        target_joints: list,
        duration: float = None,
        max_velocity: float = None,
    ) -> dict:
        """
        Move robot to target joint positions with smooth trajectory.

        Args:
            target_joints: List of 7 joint angles in radians
            duration: Optional trajectory duration (auto-computed if None)
            max_velocity: Maximum joint velocity (rad/s)
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            if len(target_joints) != self.NUM_JOINTS:
                return {
                    "success": False,
                    "error": f"Expected {self.NUM_JOINTS} joint values, got {len(target_joints)}",
                }

            target_joints = np.array(target_joints)

            # Validate joint limits
            for i, (target, lower, upper) in enumerate(
                zip(target_joints, self.JOINT_LIMITS_LOWER, self.JOINT_LIMITS_UPPER)
            ):
                if target < lower or target > upper:
                    return {
                        "success": False,
                        "error": f"Joint {i} value {target} out of limits [{lower}, {upper}]",
                    }

            # Get current state
            current_state = self.get_current_joints()
            if not current_state.get("success"):
                return current_state

            current_pos = np.array(current_state["joints"])
            current_vel = np.array(current_state["velocities"])

            vel = max_velocity if max_velocity is not None else self.max_velocity

            # Compute trajectory duration if not specified
            if duration is None:
                duration = self.traj_gen.compute_duration(
                    current_pos,
                    target_joints,
                    vel,
                    self.max_acceleration,
                )

            # Generate smooth trajectory
            positions, velocities, accelerations = self.traj_gen.quintic_trajectory(
                current_pos,
                target_joints,
                current_vel,
                np.zeros(self.NUM_JOINTS),  # End with zero velocity
                duration,
                self.time_step,
            )

            # Execute trajectory
            for i, (pos, vel, acc) in enumerate(zip(positions, velocities, accelerations)):
                # Compute torques using PD control with feedforward
                current_state = self.get_current_joints()
                if current_state.get("success"):
                    q = np.array(current_state["joints"])
                    qd = np.array(current_state["velocities"])

                    # PD control with gravity compensation
                    pos_error = pos - q
                    vel_error = vel - qd

                    # Torque = Kp * pos_error + Kd * vel_error
                    torques = self.kp * pos_error + self.kd * vel_error

                    # Clamp torques
                    torques = np.clip(torques, -self.max_force, self.max_force)

                    # Apply torques
                    p.setJointMotorControlArray(
                        self.robot_id,
                        self.arm_joint_indices,
                        p.TORQUE_CONTROL,
                        forces=torques.tolist(),
                    )

                # Step simulation
                p.stepSimulation()

                if self.gui:
                    time.sleep(self.time_step)

            # Final settling with position control
            p.setJointMotorControlArray(
                self.robot_id,
                self.arm_joint_indices,
                p.POSITION_CONTROL,
                targetPositions=target_joints.tolist(),
                forces=[self.max_force] * self.NUM_JOINTS,
                positionGains=[0.1] * self.NUM_JOINTS,
                velocityGains=[1.0] * self.NUM_JOINTS,
            )

            # Brief settling period
            for _ in range(100):
                p.stepSimulation()
                if self.gui:
                    time.sleep(self.time_step)

            return {"success": True, "message": "Movement completed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_joints(
        self,
        target_joints: list,
        max_velocity: float = None,
        wait: bool = True,
    ) -> dict:
        """
        Move robot to target joint positions (smooth version).

        Args:
            target_joints: List of 7 joint angles in radians
            max_velocity: Maximum joint velocity (rad/s)
            wait: Whether to wait for movement to complete (always True for smooth)
        """
        return self.move_joints_smooth(target_joints, max_velocity=max_velocity)

    def move_cartesian(
        self,
        target_pose: dict,
        max_velocity: float = None,
        wait: bool = True,
    ) -> dict:
        """
        Move robot to target Cartesian pose using IK.

        Args:
            target_pose: Dict with keys x, y, z, rx, ry, rz
            max_velocity: Maximum velocity
            wait: Whether to wait for movement to complete
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            required_keys = ["x", "y", "z", "rx", "ry", "rz"]
            if not all(k in target_pose for k in required_keys):
                return {"success": False, "error": f"Expected keys: {required_keys}"}

            # Convert euler to quaternion
            orientation = p.getQuaternionFromEuler([
                target_pose["rx"],
                target_pose["ry"],
                target_pose["rz"],
            ])

            position = [target_pose["x"], target_pose["y"], target_pose["z"]]

            # Calculate IK
            joint_positions = p.calculateInverseKinematics(
                self.robot_id,
                self.END_EFFECTOR_LINK,
                position,
                orientation,
                lowerLimits=self.JOINT_LIMITS_LOWER,
                upperLimits=self.JOINT_LIMITS_UPPER,
                jointRanges=[u - l for l, u in zip(self.JOINT_LIMITS_LOWER, self.JOINT_LIMITS_UPPER)],
                restPoses=self.home_position,
                maxNumIterations=100,
            )

            # Take only the first 7 joints (arm joints)
            target_joints = list(joint_positions[: self.NUM_JOINTS])

            return self.move_joints_smooth(target_joints, max_velocity=max_velocity)

        except Exception as e:
            return {"success": False, "error": str(e)}

    def control_gripper(self, command, smooth: bool = True) -> dict:
        """
        Control the gripper with smooth motion.

        Args:
            command: "open", "close", or float value 0.0-0.04 (finger width)
            smooth: Whether to use smooth motion
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            if isinstance(command, str):
                if command.lower() == "open":
                    target_width = 0.04
                elif command.lower() == "close":
                    target_width = 0.0
                else:
                    return {"success": False, "error": f"Unknown gripper command: {command}"}
            else:
                target_width = float(command)
                target_width = max(0.0, min(0.04, target_width))

            # Get current gripper position
            current_width = p.getJointState(self.robot_id, self.FINGER_JOINTS[0])[0]

            if smooth:
                # Smooth gripper motion
                steps = 200
                for i in range(steps):
                    t = (i + 1) / steps
                    # Smooth interpolation using sine
                    smooth_t = 0.5 * (1 - math.cos(math.pi * t))
                    width = current_width + smooth_t * (target_width - current_width)

                    for finger_joint in self.FINGER_JOINTS:
                        p.setJointMotorControl2(
                            self.robot_id,
                            finger_joint,
                            p.POSITION_CONTROL,
                            targetPosition=width,
                            force=20.0,
                            maxVelocity=0.5,
                        )

                    p.stepSimulation()
                    if self.gui:
                        time.sleep(self.time_step)
            else:
                # Instant gripper motion
                for finger_joint in self.FINGER_JOINTS:
                    p.setJointMotorControl2(
                        self.robot_id,
                        finger_joint,
                        p.POSITION_CONTROL,
                        targetPosition=target_width,
                        force=20.0,
                    )

                for _ in range(100):
                    p.stepSimulation()
                    if self.gui:
                        time.sleep(self.time_step)

            return {"success": True, "message": f"Gripper set to {target_width}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def go_home(self) -> dict:
        """Move robot to home position."""
        return self.move_joints_smooth(self.home_position)


def main():
    """Main entry point for DORA node."""
    node = Node()
    driver = FrankaDriverNode()

    # Auto-connect on startup
    connect_result = driver.connect()
    print(f"[FrankaDriver] Connection: {connect_result}")

    if not connect_result.get("success"):
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
                    node.send_output("status", pa.array(["moving"]))

                    # Parse joint targets
                    if isinstance(data_str, str):
                        target = json.loads(data_str)
                    else:
                        target = data_str

                    # Extract joints array and optional parameters
                    if isinstance(target, dict):
                        joints = target.get("joints", target.get("target", []))
                        vel = target.get("velocity")
                        duration = target.get("duration")
                    else:
                        joints = list(target)
                        vel = None
                        duration = None

                    result = driver.move_joints_smooth(
                        joints, duration=duration, max_velocity=vel
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
                        node.send_output("error", pa.array([json.dumps(result)]))

                elif event_id == "target_pose":
                    node.send_output("status", pa.array(["moving"]))

                    # Parse pose target
                    if isinstance(data_str, str):
                        target = json.loads(data_str)
                    else:
                        target = data_str

                    result = driver.move_cartesian(target)

                    if result.get("success"):
                        node.send_output("status", pa.array(["completed"]))
                        # Send current pose
                        pose_result = driver.get_current_pose()
                        if pose_result.get("success"):
                            node.send_output(
                                "current_pose",
                                pa.array([json.dumps(pose_result["pose"])]),
                            )
                    else:
                        node.send_output("status", pa.array(["error"]))
                        node.send_output("error", pa.array([json.dumps(result)]))

                elif event_id == "gripper":
                    # Parse gripper command
                    if isinstance(data_str, str):
                        try:
                            gripper_cmd = json.loads(data_str)
                        except json.JSONDecodeError:
                            gripper_cmd = data_str
                    else:
                        gripper_cmd = data_str

                    result = driver.control_gripper(gripper_cmd)

                    if not result.get("success"):
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
                            pa.array(["completed" if result.get("success") else "error"]),
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

                    elif cmd == "get_pose":
                        result = driver.get_current_pose()
                        if result.get("success"):
                            node.send_output(
                                "current_pose",
                                pa.array([json.dumps(result["pose"])]),
                            )
                        else:
                            node.send_output("error", pa.array([json.dumps(result)]))

                    else:
                        node.send_output("error", pa.array([f"Unknown command: {cmd}"]))

            except json.JSONDecodeError as e:
                node.send_output("error", pa.array([f"JSON parse error: {str(e)}"]))
            except Exception as e:
                node.send_output("status", pa.array(["error"]))
                node.send_output("error", pa.array([str(e)]))

        elif event_type == "STOP":
            print("[FrankaDriver] Received STOP signal")
            driver.disconnect()
            break

        elif event_type == "ERROR":
            print(f"[FrankaDriver] Error: {event}")

    print("[FrankaDriver] Node shutdown complete")


if __name__ == "__main__":
    main()
