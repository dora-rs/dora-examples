"""
DORA-RS Driver Node for UR5 Robot Arm

This node receives target joint goals and controls the UR5 robot arm via RTDE protocol.
It supports both URSim simulation and real robot modes.

Uses pure Python RTDE implementation for cross-platform compatibility (including Apple Silicon).

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
import socket
import struct
import time
from typing import Any, List, Optional, Tuple

import pyarrow as pa
from dora import Node


class RTDEClient:
    """
    Pure Python RTDE client for Universal Robots.
    Compatible with all platforms including Apple Silicon.
    """

    # RTDE command types
    RTDE_REQUEST_PROTOCOL_VERSION = 86  # 'V'
    RTDE_GET_URCONTROL_VERSION = 118  # 'v'
    RTDE_TEXT_MESSAGE = 77  # 'M'
    RTDE_DATA_PACKAGE = 85  # 'U'
    RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = 79  # 'O'
    RTDE_CONTROL_PACKAGE_SETUP_INPUTS = 73  # 'I'
    RTDE_CONTROL_PACKAGE_START = 83  # 'S'
    RTDE_CONTROL_PACKAGE_PAUSE = 80  # 'P'

    def __init__(self, host: str, port: int = 30004):
        self.host = host
        self.port = port
        self.sock = None
        self.output_recipe_id = None
        self.output_config = None

    def connect(self) -> bool:
        """Connect to RTDE interface."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))

            # Request protocol version 2
            self._send_command(self.RTDE_REQUEST_PROTOCOL_VERSION, struct.pack(">H", 2))
            cmd, payload = self._receive_command()
            if cmd != self.RTDE_REQUEST_PROTOCOL_VERSION or payload[0] != 1:
                print("[RTDE] Warning: Protocol version 2 not accepted")

            return True
        except Exception as e:
            print(f"[RTDE] Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from RTDE interface."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def setup_outputs(self, variables: List[str]) -> bool:
        """Setup output recipe."""
        recipe = ",".join(variables)
        self._send_command(
            self.RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS, recipe.encode("utf-8")
        )
        cmd, payload = self._receive_command()
        if cmd == self.RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS and len(payload) > 0:
            self.output_recipe_id = payload[0]
            self.output_config = variables
            # Check variable types (remaining bytes)
            return True
        return False

    def start(self) -> bool:
        """Start RTDE synchronization."""
        self._send_command(self.RTDE_CONTROL_PACKAGE_START, b"")
        cmd, payload = self._receive_command()
        return cmd == self.RTDE_CONTROL_PACKAGE_START and payload[0] == 1

    def receive_data(self) -> Optional[dict]:
        """Receive one data package."""
        try:
            cmd, payload = self._receive_command()
            if cmd == self.RTDE_DATA_PACKAGE and self.output_config:
                return self._parse_data_package(payload)
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[RTDE] Receive error: {e}")
        return None

    def _send_command(self, cmd_type: int, payload: bytes):
        """Send RTDE command."""
        size = len(payload) + 3  # 2 bytes size + 1 byte type + payload
        header = struct.pack(">HB", size, cmd_type)
        self.sock.sendall(header + payload)

    def _receive_command(self) -> Tuple[int, bytes]:
        """Receive RTDE command."""
        header = self._recv_all(3)
        size, cmd_type = struct.unpack(">HB", header)
        payload = self._recv_all(size - 3) if size > 3 else b""
        return cmd_type, payload

    def _recv_all(self, n: int) -> bytes:
        """Receive exactly n bytes."""
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def _parse_data_package(self, payload: bytes) -> dict:
        """Parse data package based on output recipe."""
        result = {}
        offset = 1  # Skip recipe ID byte

        for var in self.output_config:
            if var.startswith("actual_q") or var.startswith("actual_TCP_pose"):
                # 6 doubles (48 bytes)
                values = struct.unpack_from(">6d", payload, offset)
                result[var] = list(values)
                offset += 48
            elif var.startswith("actual_") and "speed" in var:
                # 6 doubles
                values = struct.unpack_from(">6d", payload, offset)
                result[var] = list(values)
                offset += 48
            elif var == "robot_mode" or var == "safety_mode":
                # int32
                result[var] = struct.unpack_from(">i", payload, offset)[0]
                offset += 4
            elif var == "timestamp":
                # double
                result[var] = struct.unpack_from(">d", payload, offset)[0]
                offset += 8
            else:
                # Default: try double
                try:
                    result[var] = struct.unpack_from(">d", payload, offset)[0]
                    offset += 8
                except struct.error:
                    break

        return result


class URScriptClient:
    """Client for sending URScript commands via Primary/Secondary interface."""

    def __init__(self, host: str, port: int = 30002):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self) -> bool:
        """Connect to UR secondary interface."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"[URScript] Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def send_script(self, script: str) -> bool:
        """Send URScript program."""
        try:
            if not script.endswith("\n"):
                script += "\n"
            self.sock.sendall(script.encode("utf-8"))
            return True
        except Exception as e:
            print(f"[URScript] Send error: {e}")
            return False

    def movej(
        self, joints: List[float], a: float = 0.5, v: float = 0.3, t: float = 0, r: float = 0
    ) -> bool:
        """Send moveJ command."""
        q_str = "[" + ",".join(f"{j:.6f}" for j in joints) + "]"
        script = f"movej({q_str}, a={a}, v={v}, t={t}, r={r})"
        return self.send_script(script)

    def movel(
        self, pose: List[float], a: float = 0.5, v: float = 0.3, t: float = 0, r: float = 0
    ) -> bool:
        """Send moveL command."""
        p_str = "p[" + ",".join(f"{p:.6f}" for p in pose) + "]"
        script = f"movel({p_str}, a={a}, v={v}, t={t}, r={r})"
        return self.send_script(script)

    def stopj(self, a: float = 2.0) -> bool:
        """Send stopj command."""
        return self.send_script(f"stopj({a})")


class UR5DriverNode:
    """DORA driver node for UR5 robot arm control via RTDE."""

    def __init__(self):
        self.rtde = None
        self.urscript = None
        self.ip = os.getenv("UR5_IP", "127.0.0.1")
        self.acceleration = float(os.getenv("UR5_ACCELERATION", "0.5"))
        self.velocity = float(os.getenv("UR5_VELOCITY", "0.3"))
        self.connected = False

        # Home position (6-axis joint angles in radians)
        self.home_position = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]

        # Output variables to receive
        self.output_vars = ["actual_q", "actual_TCP_pose", "robot_mode"]

    def connect(self) -> dict:
        """Connect to the UR5 robot via RTDE."""
        try:
            # Connect RTDE for reading state
            self.rtde = RTDEClient(self.ip)
            if not self.rtde.connect():
                return {"success": False, "error": f"RTDE connection failed to {self.ip}"}

            # Setup output recipe
            if not self.rtde.setup_outputs(self.output_vars):
                return {"success": False, "error": "Failed to setup RTDE outputs"}

            # Start synchronization
            if not self.rtde.start():
                return {"success": False, "error": "Failed to start RTDE sync"}

            # Connect URScript for sending commands
            self.urscript = URScriptClient(self.ip)
            if not self.urscript.connect():
                return {"success": False, "error": f"URScript connection failed to {self.ip}"}

            self.connected = True
            return {"success": True, "message": f"Connected to UR5 at {self.ip}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disconnect(self) -> dict:
        """Disconnect from the robot."""
        try:
            if self.rtde:
                self.rtde.disconnect()
            if self.urscript:
                self.urscript.disconnect()
            self.connected = False
            return {"success": True, "message": "Disconnected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_current_joints(self) -> dict:
        """Get current joint positions."""
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}
            data = self.rtde.receive_data()
            if data and "actual_q" in data:
                return {"success": True, "joints": data["actual_q"]}
            return {"success": False, "error": "No data received"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_current_pose(self) -> dict:
        """Get current TCP pose."""
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}
            data = self.rtde.receive_data()
            if data and "actual_TCP_pose" in data:
                pose = data["actual_TCP_pose"]
                return {
                    "success": True,
                    "pose": {
                        "x": pose[0],
                        "y": pose[1],
                        "z": pose[2],
                        "rx": pose[3],
                        "ry": pose[4],
                        "rz": pose[5],
                    },
                }
            return {"success": False, "error": "No data received"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_joints(
        self,
        target_joints: list,
        acceleration: float = None,
        velocity: float = None,
        wait: bool = True,
    ) -> dict:
        """Move robot to target joint positions using moveJ."""
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected"}

            if len(target_joints) != 6:
                return {"success": False, "error": "Expected 6 joint values"}

            acc = acceleration if acceleration is not None else self.acceleration
            vel = velocity if velocity is not None else self.velocity

            # Send moveJ command
            if not self.urscript.movej(target_joints, a=acc, v=vel):
                return {"success": False, "error": "Failed to send moveJ"}

            if wait:
                # Wait for movement to complete by checking joint positions
                time.sleep(0.5)  # Initial delay
                tolerance = 0.01  # radians
                timeout = 30  # seconds
                start_time = time.time()

                while time.time() - start_time < timeout:
                    data = self.rtde.receive_data()
                    if data and "actual_q" in data:
                        current = data["actual_q"]
                        if all(
                            abs(current[i] - target_joints[i]) < tolerance
                            for i in range(6)
                        ):
                            return {"success": True, "message": "Movement completed"}
                    time.sleep(0.1)

                return {"success": True, "message": "Movement sent (timeout waiting)"}

            return {"success": True, "message": "Movement command sent"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_linear(
        self,
        target_pose: dict,
        acceleration: float = None,
        velocity: float = None,
        wait: bool = True,
    ) -> dict:
        """Move robot linearly to target Cartesian pose using moveL."""
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

            if not self.urscript.movel(pose, a=acc, v=vel):
                return {"success": False, "error": "Failed to send moveL"}

            if wait:
                time.sleep(0.5)
                tolerance = 0.001  # meters/radians
                timeout = 30
                start_time = time.time()

                while time.time() - start_time < timeout:
                    data = self.rtde.receive_data()
                    if data and "actual_TCP_pose" in data:
                        current = data["actual_TCP_pose"]
                        if all(abs(current[i] - pose[i]) < tolerance for i in range(6)):
                            return {"success": True, "message": "Linear movement completed"}
                    time.sleep(0.1)

                return {"success": True, "message": "Movement sent (timeout waiting)"}

            return {"success": True, "message": "Movement command sent"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_movement(self) -> dict:
        """Stop any ongoing movement."""
        try:
            if self.urscript and self.connected:
                self.urscript.stopj(2.0)
            return {"success": True, "message": "Movement stopped"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def go_home(self) -> dict:
        """Move robot to home position."""
        return self.move_joints(self.home_position)


def main():
    """Main entry point for DORA node."""
    node = Node()
    driver = UR5DriverNode()

    # Auto-connect on startup
    connect_result = driver.connect()
    print(f"[UR5Driver] Connection: {connect_result}")

    if not connect_result.get("success"):
        node.send_output("error", pa.array([json.dumps(connect_result)]))

    node.send_output("status", pa.array(["idle"]))

    for event in node:
        event_type = event["type"]

        if event_type == "INPUT":
            event_id = event["id"]
            data = event["value"]

            try:
                if hasattr(data, "to_pylist"):
                    data_list = data.to_pylist()
                    if data_list:
                        data_str = data_list[0]
                    else:
                        continue
                else:
                    data_str = str(data)

                if event_id == "target_joints":
                    node.send_output("status", pa.array(["moving"]))

                    if isinstance(data_str, str):
                        target = json.loads(data_str)
                    else:
                        target = data_str

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

                    if isinstance(data_str, str):
                        target = json.loads(data_str)
                    else:
                        target = data_str

                    result = driver.move_linear(target)

                    if result.get("success"):
                        node.send_output("status", pa.array(["completed"]))
                    else:
                        node.send_output("status", pa.array(["error"]))
                        node.send_output("error", pa.array([json.dumps(result)]))

                elif event_id == "command":
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
                        driver.stop_movement()
                        driver.disconnect()
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
            print("[UR5Driver] Received STOP signal")
            driver.stop_movement()
            driver.disconnect()
            break

        elif event_type == "ERROR":
            print(f"[UR5Driver] Error: {event}")

    print("[UR5Driver] Node shutdown complete")


if __name__ == "__main__":
    main()
