#!/usr/bin/env python3
"""
IMU Synthesizer for DORA Simulation

Generates synthetic IMU data from vehicle state (pose and velocity).

Inputs:
    - sim_state: Vehicle state [x, y, theta, velocity, steering, accel, yaw_rate]

Outputs:
    - imu_msg: Synthesized IMU message compatible with real IMU format
"""

import math
import yaml
import os
from pathlib import Path

import numpy as np
import pyarrow as pa
from dora import DoraStatus


class IMUSynthesizer:
    """Synthesize IMU data from vehicle motion."""

    def __init__(self, config_path: str = None):
        # Load configuration
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                imu_config = config.get('imu', {})
                sim_config = config.get('simulation', {})
        else:
            imu_config = {}
            sim_config = {}

        # IMU parameters
        self.accel_noise_std = imu_config.get('accel_noise_std', 0.01)
        self.gyro_noise_std = imu_config.get('gyro_noise_std', 0.001)
        self.accel_bias = np.array(imu_config.get('accel_bias', [0.0, 0.0, 0.0]))
        self.gyro_bias = np.array(imu_config.get('gyro_bias', [0.0, 0.0, 0.0]))

        self.dt = sim_config.get('dt', 0.02)
        self.gravity = 9.81

        # State history
        self.prev_vx = 0.0
        self.prev_vy = 0.0

    def synthesize(self, state: dict) -> dict:
        """Synthesize IMU data from vehicle state."""
        theta = state.get('theta', 0.0)
        velocity = state.get('velocity', 0.0)
        yaw_rate = state.get('yaw_rate', 0.0)

        # Velocity components in world frame
        vx = velocity * math.cos(theta)
        vy = velocity * math.sin(theta)

        # Acceleration in world frame
        ax_world = (vx - self.prev_vx) / self.dt if self.dt > 0 else 0.0
        ay_world = (vy - self.prev_vy) / self.dt if self.dt > 0 else 0.0

        # Transform to body frame
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        ax_body = ax_world * cos_theta + ay_world * sin_theta
        ay_body = -ax_world * sin_theta + ay_world * cos_theta
        az_body = self.gravity

        # Add noise
        ax_noisy = ax_body + np.random.normal(0, self.accel_noise_std) + self.accel_bias[0]
        ay_noisy = ay_body + np.random.normal(0, self.accel_noise_std) + self.accel_bias[1]
        az_noisy = az_body + np.random.normal(0, self.accel_noise_std) + self.accel_bias[2]

        yaw_rate_noisy = yaw_rate + np.random.normal(0, self.gyro_noise_std) + self.gyro_bias[2]

        # Update history
        self.prev_vx = vx
        self.prev_vy = vy

        return {
            'roll': 0.0,
            'pitch': 0.0,
            'yaw': math.degrees(theta),
            'gyro_x': 0.0,
            'gyro_y': 0.0,
            'gyro_z': yaw_rate_noisy,
            'accel_x': ax_noisy,
            'accel_y': ay_noisy,
            'accel_z': az_noisy,
        }


class Operator:
    """DORA Operator for IMU Synthesizer."""

    def __init__(self):
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "vehicle_params.yaml"
        self.synthesizer = IMUSynthesizer(str(config_path))
        print(f"[IMUSynthesizer] Initialized: noise_accel={self.synthesizer.accel_noise_std}, noise_gyro={self.synthesizer.gyro_noise_std}")

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "sim_state":
                data = dora_event["value"].to_pylist()

                if len(data) >= 7:
                    state = {
                        'x': data[0],
                        'y': data[1],
                        'theta': data[2],
                        'velocity': data[3],
                        'steering_angle': data[4],
                        'acceleration': data[5],
                        'yaw_rate': data[6],
                    }

                    imu_data = self.synthesizer.synthesize(state)

                    imu_array = [
                        imu_data['roll'], imu_data['pitch'], imu_data['yaw'],
                        imu_data['gyro_x'], imu_data['gyro_y'], imu_data['gyro_z'],
                        imu_data['accel_x'], imu_data['accel_y'], imu_data['accel_z']
                    ]
                    send_output(
                        "imu_msg",
                        pa.array(imu_array, type=pa.float32()),
                        dora_event["metadata"]
                    )

        elif dora_event["type"] == "STOP":
            print("[IMUSynthesizer] Stopped")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
