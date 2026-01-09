#!/usr/bin/env python3
"""
Bicycle Model Vehicle Simulator for DORA

This operator implements a kinematic bicycle model that simulates
vehicle motion based on steering and throttle/brake commands.

Inputs:
    - steering_cmd: Steering angle command (float32)
    - throttle_cmd: Throttle/brake command (float32, -1 to 1)
    - tick: Timer trigger for simulation step

Outputs:
    - sim_pose: Simulated vehicle pose [x, y, theta, velocity] (float32 array)
    - sim_state: Full vehicle state for debugging (float32 array)
"""

import math
import yaml
import os
from pathlib import Path

import pyarrow as pa
from dora import DoraStatus


class BicycleModel:
    """Kinematic bicycle model for vehicle simulation."""

    def __init__(self, config_path: str = None):
        # Load configuration
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                vehicle = config.get('vehicle', {})
                sim = config.get('simulation', {})
        else:
            vehicle = {}
            sim = {}

        # Vehicle parameters
        self.wheelbase = vehicle.get('wheelbase', 0.5)
        self.max_speed = vehicle.get('max_speed', 2.0)
        self.min_speed = vehicle.get('min_speed', -0.5)
        self.max_accel = vehicle.get('max_acceleration', 1.0)
        self.max_decel = vehicle.get('max_deceleration', 2.0)
        self.max_steering = vehicle.get('max_steering_angle', 0.5)
        self.max_steering_rate = vehicle.get('max_steering_rate', 1.0)

        # Simulation parameters
        self.dt = sim.get('dt', 0.02)

        # Vehicle state
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.velocity = 0.0
        self.steering_angle = 0.0

        # Command inputs
        self.steering_cmd = 0.0
        self.throttle_cmd = 0.0

        # Previous state for IMU synthesis
        self.prev_velocity = 0.0
        self.prev_theta = 0.0

    def set_initial_state(self, x: float, y: float, theta: float, velocity: float = 0.0):
        """Set initial vehicle state."""
        self.x = x
        self.y = y
        self.theta = theta
        self.velocity = velocity
        self.prev_velocity = velocity
        self.prev_theta = theta

    def step(self) -> dict:
        """Execute one simulation step."""
        # Save previous state
        self.prev_velocity = self.velocity
        self.prev_theta = self.theta

        # Apply steering with rate limit
        steering_error = self.steering_cmd - self.steering_angle
        max_delta = self.max_steering_rate * self.dt
        steering_delta = max(-max_delta, min(max_delta, steering_error))
        self.steering_angle += steering_delta
        self.steering_angle = max(-self.max_steering, min(self.max_steering, self.steering_angle))

        # Apply throttle/brake to velocity
        if self.throttle_cmd >= 0:
            accel = self.throttle_cmd * self.max_accel
        else:
            accel = self.throttle_cmd * self.max_decel

        self.velocity += accel * self.dt
        self.velocity = max(self.min_speed, min(self.max_speed, self.velocity))

        # Bicycle model kinematics
        if abs(self.steering_angle) > 1e-6:
            turn_radius = self.wheelbase / math.tan(self.steering_angle)
            angular_velocity = self.velocity / turn_radius
        else:
            angular_velocity = 0.0

        # Update pose
        self.theta += angular_velocity * self.dt
        while self.theta > math.pi:
            self.theta -= 2 * math.pi
        while self.theta < -math.pi:
            self.theta += 2 * math.pi

        self.x += self.velocity * math.cos(self.theta) * self.dt
        self.y += self.velocity * math.sin(self.theta) * self.dt

        return {
            'x': self.x,
            'y': self.y,
            'theta': self.theta,
            'velocity': self.velocity,
            'steering_angle': self.steering_angle,
            'acceleration': (self.velocity - self.prev_velocity) / self.dt if self.dt > 0 else 0.0,
            'yaw_rate': (self.theta - self.prev_theta) / self.dt if self.dt > 0 else 0.0,
        }


class Operator:
    """DORA Operator for Bicycle Model."""

    def __init__(self):
        # Find config file
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "vehicle_params.yaml"
        sim_config_path = script_dir / "config" / "sim_config.yaml"

        # Initialize bicycle model
        self.model = BicycleModel(str(config_path))

        # Load initial state
        if sim_config_path.exists():
            with open(sim_config_path, 'r') as f:
                sim_config = yaml.safe_load(f)
                init = sim_config.get('initial_state', {})
                self.model.set_initial_state(
                    x=init.get('x', 0.0),
                    y=init.get('y', 0.0),
                    theta=init.get('theta', 0.0),
                    velocity=init.get('velocity', 0.0)
                )

        print(f"[BicycleModel] Initialized: wheelbase={self.model.wheelbase}m, max_speed={self.model.max_speed}m/s")
        print(f"[BicycleModel] Initial pose: ({self.model.x:.2f}, {self.model.y:.2f}, {math.degrees(self.model.theta):.1f}deg)")

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "steering_cmd":
                data = dora_event["value"].to_pylist()
                if data:
                    self.model.steering_cmd = float(data[0])

            elif event_id == "throttle_cmd":
                data = dora_event["value"].to_pylist()
                if data:
                    self.model.throttle_cmd = float(data[0])

            elif event_id == "tick":
                # Execute simulation step
                state = self.model.step()

                # Send pose output [x, y, theta, velocity]
                pose_data = [state['x'], state['y'], state['theta'], state['velocity']]
                send_output(
                    "sim_pose",
                    pa.array(pose_data, type=pa.float32()),
                    dora_event["metadata"]
                )

                # Send full state
                state_data = [
                    state['x'], state['y'], state['theta'],
                    state['velocity'], state['steering_angle'],
                    state['acceleration'], state['yaw_rate']
                ]
                send_output(
                    "sim_state",
                    pa.array(state_data, type=pa.float32()),
                    dora_event["metadata"]
                )

        elif dora_event["type"] == "STOP":
            print("[BicycleModel] Stopped")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
