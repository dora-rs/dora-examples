#!/usr/bin/env python3
"""
Simulation Visualizer for DORA using Rerun

Provides 3D visualization of the simulation including:
- Vehicle position and orientation
- Planned path
- Vehicle trail (history)

Inputs:
    - sim_pose: Vehicle pose [x, y, theta, velocity]
    - waypoints: Path waypoints [x1, y1, x2, y2, ...]
    - target_point: Current target point [x, y]
"""

import math
import yaml
import os
from pathlib import Path
from collections import deque

import numpy as np
import rerun as rr
from dora import DoraStatus


class SimulationVisualizer:
    """Rerun-based visualization for simulation."""

    def __init__(self, config_path: str = None):
        # Load configuration
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                viz_config = config.get('visualization', {})
        else:
            viz_config = {}

        # Vehicle dimensions
        self.vehicle_length = viz_config.get('vehicle_length', 0.6)
        self.vehicle_width = viz_config.get('vehicle_width', 0.4)
        self.vehicle_height = viz_config.get('vehicle_height', 0.3)

        # Trail settings
        self.trail_length = viz_config.get('trail_length', 200)
        self.trail = deque(maxlen=self.trail_length)

        # Colors
        self.vehicle_color = [255, 200, 0, 255]
        self.trail_color = [255, 128, 0, 200]
        self.path_color = [0, 200, 255, 255]
        self.target_color = [255, 0, 255, 255]

        self.waypoints_logged = False

    def log_ground_plane(self, size: float = 20.0):
        """Log ground plane grid."""
        lines = []
        step = 2.0
        for i in np.arange(-size, size + step, step):
            lines.append([[i, -size, 0], [i, size, 0]])
            lines.append([[-size, i, 0], [size, i, 0]])

        rr.log(
            "world/ground_grid",
            rr.LineStrips3D(lines, colors=[[100, 100, 100, 50]]),
            static=True
        )

    def log_waypoints(self, waypoints: list):
        """Log path waypoints."""
        if len(waypoints) < 2:
            return

        points_3d = [[wp[0], wp[1], 0.05] for wp in waypoints]

        rr.log(
            "world/path",
            rr.LineStrips3D([points_3d], colors=[self.path_color], radii=[0.05])
        )

        rr.log(
            "world/waypoints",
            rr.Points3D(points_3d, colors=[self.path_color], radii=[0.1])
        )

        self.waypoints_logged = True

    def log_vehicle(self, x: float, y: float, theta: float, velocity: float):
        """Log vehicle position and orientation."""
        self.trail.append([x, y, 0.02])

        # Trail
        if len(self.trail) > 1:
            rr.log(
                "world/vehicle_trail",
                rr.LineStrips3D([list(self.trail)], colors=[self.trail_color], radii=[0.03])
            )

        # Vehicle box
        center = [x, y, self.vehicle_height / 2]
        half_sizes = [self.vehicle_length / 2, self.vehicle_width / 2, self.vehicle_height / 2]

        qw = math.cos(theta / 2)
        qz = math.sin(theta / 2)
        rotation = rr.Quaternion(xyzw=[0, 0, qz, qw])

        rr.log(
            "world/vehicle",
            rr.Boxes3D(
                centers=[center],
                half_sizes=[half_sizes],
                rotations=[rotation],
                colors=[self.vehicle_color],
                labels=[f"v={velocity:.2f}m/s"]
            )
        )

        # Direction arrow
        arrow_length = 0.8
        rr.log(
            "world/vehicle_direction",
            rr.Arrows3D(
                origins=[[x, y, self.vehicle_height]],
                vectors=[[arrow_length * math.cos(theta), arrow_length * math.sin(theta), 0]],
                colors=[[255, 0, 0, 255]],
                radii=[0.05]
            )
        )

    def log_target_point(self, x: float, y: float):
        """Log current target point."""
        rr.log(
            "world/target",
            rr.Points3D([[x, y, 0.1]], colors=[self.target_color], radii=[0.15])
        )


def load_waypoints(file_path: str) -> list:
    """Load waypoints from file."""
    waypoints = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        waypoints.append([float(parts[0]), float(parts[1])])
    except Exception as e:
        print(f"[Visualizer] Could not load waypoints: {e}")
    return waypoints


class Operator:
    """DORA Operator for Simulation Visualizer."""

    def __init__(self):
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "vehicle_params.yaml"
        sim_config_path = script_dir / "config" / "sim_config.yaml"

        # Initialize Rerun
        rr.init("DORA_NAV_Simulation")
        rr.spawn()

        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)

        self.visualizer = SimulationVisualizer(str(config_path))
        self.visualizer.log_ground_plane(size=15.0)

        # Load waypoints
        if sim_config_path.exists():
            with open(sim_config_path, 'r') as f:
                sim_config = yaml.safe_load(f)
                paths_config = sim_config.get('paths', {})
                waypoints_file = paths_config.get('waypoints_file', '')

                if waypoints_file:
                    waypoints_path = script_dir / waypoints_file
                    waypoints = load_waypoints(str(waypoints_path))
                    if waypoints:
                        self.visualizer.log_waypoints(waypoints)
                        print(f"[Visualizer] Loaded {len(waypoints)} waypoints")

        print("[Visualizer] Initialized - Rerun window should open")

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "sim_pose":
                data = dora_event["value"].to_pylist()
                if len(data) >= 4:
                    self.visualizer.log_vehicle(data[0], data[1], data[2], data[3])

            elif event_id == "waypoints":
                data = dora_event["value"].to_pylist()
                if len(data) >= 4:
                    waypoints = [[data[i], data[i+1]] for i in range(0, len(data)-1, 2)]
                    self.visualizer.log_waypoints(waypoints)

            elif event_id == "target_point":
                data = dora_event["value"].to_pylist()
                if len(data) >= 2:
                    self.visualizer.log_target_point(data[0], data[1])

        elif dora_event["type"] == "STOP":
            print("[Visualizer] Stopped")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
