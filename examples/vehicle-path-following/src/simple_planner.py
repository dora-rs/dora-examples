#!/usr/bin/env python3
"""
Simple Path Following Planner for DORA Simulation

Implements pure pursuit path following algorithm.

Inputs:
    - sim_pose: Current vehicle pose [x, y, theta, velocity]

Outputs:
    - steering_cmd: Steering angle command (float32)
    - throttle_cmd: Throttle/brake command (float32)
    - target_point: Current lookahead point [x, y]
    - waypoints: Path waypoints for visualization
"""

import math
import yaml
import os
from pathlib import Path

import numpy as np
import pyarrow as pa
from dora import DoraStatus


class PurePursuitController:
    """Pure pursuit path following controller."""

    def __init__(self, config_path: str = None):
        # Load configuration
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                vehicle = config.get('vehicle', {})
                controller = config.get('controller', {})
        else:
            vehicle = {}
            controller = {}

        self.wheelbase = vehicle.get('wheelbase', 0.5)
        self.max_steering = vehicle.get('max_steering_angle', 0.5)
        self.max_speed = vehicle.get('max_speed', 2.0)

        self.lookahead_distance = controller.get('lookahead_distance', 1.0)
        self.min_lookahead = controller.get('min_lookahead', 0.5)
        self.max_lookahead = controller.get('max_lookahead', 3.0)
        self.lookahead_ratio = controller.get('lookahead_ratio', 0.5)
        self.goal_tolerance = controller.get('goal_tolerance', 0.3)
        self.speed_target = controller.get('speed_target', 1.0)

        self.waypoints = []
        self.current_waypoint_idx = 0
        self.goal_reached = False
        self.target_point = None

    def load_waypoints(self, file_path: str) -> bool:
        """Load waypoints from file."""
        self.waypoints = []
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2:
                            self.waypoints.append(np.array([float(parts[0]), float(parts[1])]))
            print(f"[Planner] Loaded {len(self.waypoints)} waypoints")
            return len(self.waypoints) > 0
        except Exception as e:
            print(f"[Planner] Error loading waypoints: {e}")
            return False

    def find_closest_waypoint_idx(self, x: float, y: float) -> int:
        """Find index of closest waypoint to current position."""
        pos = np.array([x, y])
        min_dist = float('inf')
        closest_idx = 0

        for i, wp in enumerate(self.waypoints):
            dist = np.linalg.norm(wp - pos)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i

        return closest_idx

    def find_lookahead_point(self, x: float, y: float, velocity: float) -> tuple:
        """Find the lookahead point on the path."""
        if not self.waypoints or self.goal_reached:
            return None, -1

        pos = np.array([x, y])

        # Always find closest waypoint first to handle path deviation
        closest_idx = self.find_closest_waypoint_idx(x, y)

        # Only allow moving forward on path (prevent going backwards)
        if closest_idx > self.current_waypoint_idx:
            self.current_waypoint_idx = closest_idx

        lookahead = self.min_lookahead + self.lookahead_ratio * abs(velocity)
        lookahead = max(self.min_lookahead, min(self.max_lookahead, lookahead))

        # Search from closest waypoint forward
        for i in range(self.current_waypoint_idx, len(self.waypoints)):
            wp = self.waypoints[i]
            dist = np.linalg.norm(wp - pos)

            if dist >= lookahead:
                self.current_waypoint_idx = i
                return wp, i

        # Near end of path
        if len(self.waypoints) > 0:
            last_wp = self.waypoints[-1]
            dist_to_goal = np.linalg.norm(last_wp - pos)

            if dist_to_goal < self.goal_tolerance:
                self.goal_reached = True
                print("[Planner] Goal reached!")
                return None, -1

            return last_wp, len(self.waypoints) - 1

        return None, -1

    def compute_steering(self, x: float, y: float, theta: float,
                         target_x: float, target_y: float) -> float:
        """Compute steering angle using pure pursuit."""
        dx = target_x - x
        dy = target_y - y

        local_x = dx * math.cos(theta) + dy * math.sin(theta)
        local_y = -dx * math.sin(theta) + dy * math.cos(theta)

        lookahead_dist = math.sqrt(local_x**2 + local_y**2)

        if lookahead_dist < 0.01:
            return 0.0

        curvature = 2 * local_y / (lookahead_dist**2)
        steering = math.atan(self.wheelbase * curvature)
        steering = max(-self.max_steering, min(self.max_steering, steering))

        return steering

    def compute_throttle(self, velocity: float, distance_to_goal: float) -> float:
        """Compute throttle command."""
        if self.goal_reached:
            return -0.5

        target_speed = self.speed_target

        if distance_to_goal < 2.0:
            target_speed = max(0.3, target_speed * (distance_to_goal / 2.0))

        speed_error = target_speed - velocity
        throttle = 0.5 * speed_error
        throttle = max(-1.0, min(1.0, throttle))

        return throttle

    def step(self, x: float, y: float, theta: float, velocity: float) -> dict:
        """Compute control commands for current state."""
        if self.goal_reached or not self.waypoints:
            # Brake only if moving forward, otherwise hold position
            if velocity > 0.05:
                throttle = -0.5  # Gentle brake when moving forward
            elif velocity < -0.05:
                throttle = 0.3   # Accelerate forward if moving backward
            else:
                throttle = 0.0   # Hold position when stopped

            return {
                'steering': 0.0,
                'throttle': throttle,
                'target_point': None,
                'goal_reached': self.goal_reached
            }

        target, idx = self.find_lookahead_point(x, y, velocity)

        if target is None:
            return {
                'steering': 0.0,
                'throttle': -0.3,
                'target_point': None,
                'goal_reached': True
            }

        self.target_point = target
        steering = self.compute_steering(x, y, theta, target[0], target[1])

        goal = self.waypoints[-1]
        dist_to_goal = np.linalg.norm(goal - np.array([x, y]))
        throttle = self.compute_throttle(velocity, dist_to_goal)

        return {
            'steering': steering,
            'throttle': throttle,
            'target_point': target,
            'goal_reached': False,
            'distance_to_goal': dist_to_goal
        }

    def get_waypoints_flat(self) -> list:
        """Get waypoints as flat list."""
        flat = []
        for wp in self.waypoints:
            flat.extend([float(wp[0]), float(wp[1])])
        return flat


class Operator:
    """DORA Operator for Simple Planner."""

    def __init__(self):
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "vehicle_params.yaml"
        sim_config_path = script_dir / "config" / "sim_config.yaml"

        self.controller = PurePursuitController(str(config_path))

        # Load waypoints
        if sim_config_path.exists():
            with open(sim_config_path, 'r') as f:
                sim_config = yaml.safe_load(f)
                paths_config = sim_config.get('paths', {})
                waypoints_file = paths_config.get('waypoints_file', '')

                if waypoints_file:
                    waypoints_path = script_dir / waypoints_file
                    self.controller.load_waypoints(str(waypoints_path))

        self.waypoints_sent = False

        print(f"[Planner] Initialized: lookahead={self.controller.lookahead_distance}m, speed={self.controller.speed_target}m/s")

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "sim_pose":
                data = dora_event["value"].to_pylist()

                if len(data) >= 4:
                    x, y, theta, velocity = data[0], data[1], data[2], data[3]

                    result = self.controller.step(x, y, theta, velocity)

                    send_output(
                        "steering_cmd",
                        pa.array([result['steering']], type=pa.float32()),
                        dora_event["metadata"]
                    )

                    send_output(
                        "throttle_cmd",
                        pa.array([result['throttle']], type=pa.float32()),
                        dora_event["metadata"]
                    )

                    if result['target_point'] is not None:
                        send_output(
                            "target_point",
                            pa.array([float(result['target_point'][0]), float(result['target_point'][1])], type=pa.float32()),
                            dora_event["metadata"]
                        )

                    if not self.waypoints_sent and self.controller.waypoints:
                        waypoints_flat = self.controller.get_waypoints_flat()
                        send_output(
                            "waypoints",
                            pa.array(waypoints_flat, type=pa.float32()),
                            dora_event["metadata"]
                        )
                        self.waypoints_sent = True

        elif dora_event["type"] == "STOP":
            print("[Planner] Stopped")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
