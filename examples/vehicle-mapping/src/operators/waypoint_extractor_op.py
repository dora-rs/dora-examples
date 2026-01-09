#!/usr/bin/env python3
"""
Waypoint Extractor Operator for DORA

Extracts waypoints from the trajectory for path following.

Inputs:
    - pose: SE3 pose as flattened 4x4 matrix
    - map_complete: Signal when mapping is done

Outputs:
    - waypoints: Extracted waypoints as flattened array [x1,y1, x2,y2, ...]
    - trajectory: Full trajectory as flattened array
"""

import os
from pathlib import Path
import numpy as np
import pyarrow as pa
from dora import DoraStatus


class Operator:
    """DORA Operator for Waypoint Extraction."""

    def __init__(self):
        # Load configuration
        config_path = Path(__file__).parent.parent.parent / 'config' / 'mapping_config.yaml'
        self.config = self._load_config(config_path)

        # Waypoint extraction parameters
        wp_config = self.config.get('waypoints', {})
        self.min_spacing = wp_config.get('min_spacing', 0.5)
        self.simplify = wp_config.get('simplify', False)
        self.epsilon = wp_config.get('epsilon', 0.1)

        # Output directory
        self.output_dir = Path(os.environ.get(
            'MAP_OUTPUT_DIR',
            str(Path(__file__).parent.parent.parent / 'output' / 'dora_map')
        ))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # State
        self.poses = []
        self.waypoints_extracted = False

        print(f"[WaypointExtractor] Initialized: spacing={self.min_spacing}m, simplify={self.simplify}")

    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        if config_path.exists():
            try:
                import yaml
                with open(config_path) as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {}

    def _douglas_peucker(self, points: np.ndarray, epsilon: float) -> np.ndarray:
        """Simplify trajectory using Douglas-Peucker algorithm."""
        if len(points) <= 2:
            return points

        # Find point with maximum distance from line
        start, end = points[0], points[-1]
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)

        if line_len < 1e-6:
            return np.array([start, end])

        line_unit = line_vec / line_len

        max_dist = 0
        max_idx = 0
        for i in range(1, len(points) - 1):
            vec = points[i] - start
            proj_len = np.dot(vec, line_unit)
            proj = start + proj_len * line_unit
            dist = np.linalg.norm(points[i] - proj)

            if dist > max_dist:
                max_dist = dist
                max_idx = i

        # Recursively simplify
        if max_dist > epsilon:
            left = self._douglas_peucker(points[:max_idx + 1], epsilon)
            right = self._douglas_peucker(points[max_idx:], epsilon)
            return np.vstack([left[:-1], right])
        else:
            return np.array([start, end])

    def _extract_waypoints(self) -> np.ndarray:
        """Extract waypoints from trajectory."""
        if len(self.poses) == 0:
            return np.zeros((0, 2))

        # Extract XY positions from poses
        trajectory = np.array([[p[0, 3], p[1, 3]] for p in self.poses])

        if self.simplify:
            # Use Douglas-Peucker simplification
            waypoints = self._douglas_peucker(trajectory, self.epsilon)
        else:
            # Use minimum spacing
            waypoints = [trajectory[0]]
            for i in range(1, len(trajectory)):
                dist = np.linalg.norm(trajectory[i] - waypoints[-1])
                if dist >= self.min_spacing:
                    waypoints.append(trajectory[i])

            # Always include last point
            if len(waypoints) > 0:
                last_dist = np.linalg.norm(trajectory[-1] - waypoints[-1])
                if last_dist > 0.1:
                    waypoints.append(trajectory[-1])

            waypoints = np.array(waypoints)

        return waypoints

    def _save_outputs(self, waypoints: np.ndarray, trajectory: np.ndarray):
        """Save waypoints and trajectory to files."""
        # Save waypoints
        wp_path = self.output_dir / 'waypoints.txt'
        with open(wp_path, 'w') as f:
            f.write("# Waypoints extracted from DORA mapping\n")
            f.write("# Format: x y (meters)\n")
            f.write(f"# Total waypoints: {len(waypoints)}\n\n")
            for x, y in waypoints:
                f.write(f"{x:.4f} {y:.4f}\n")

        # Save trajectory
        traj_path = self.output_dir / 'trajectory.txt'
        with open(traj_path, 'w') as f:
            f.write("# Trajectory from DORA mapping\n")
            f.write("# Format: id x y z qx qy qz qw\n\n")
            for i, pose in enumerate(self.poses):
                x, y, z = pose[:3, 3]
                # Extract quaternion from rotation matrix
                qw = np.sqrt(1 + pose[0, 0] + pose[1, 1] + pose[2, 2]) / 2
                qw = max(qw, 1e-6)
                qx = (pose[2, 1] - pose[1, 2]) / (4 * qw)
                qy = (pose[0, 2] - pose[2, 0]) / (4 * qw)
                qz = (pose[1, 0] - pose[0, 1]) / (4 * qw)
                f.write(f"{i} {x:.6f} {y:.6f} {z:.6f} {qx:.6f} {qy:.6f} {qz:.6f} {qw:.6f}\n")

        print(f"[WaypointExtractor] Saved {len(waypoints)} waypoints to {wp_path}")
        print(f"[WaypointExtractor] Saved trajectory to {traj_path}")

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "pose":
                # Accumulate poses
                pose_flat = dora_event["value"].to_numpy()
                if len(pose_flat) == 16:
                    pose = pose_flat.reshape(4, 4)
                    self.poses.append(pose)

            elif event_id == "map_complete":
                if not self.waypoints_extracted and len(self.poses) > 0:
                    # Extract waypoints
                    waypoints = self._extract_waypoints()

                    # Extract trajectory
                    trajectory = np.array([[p[0, 3], p[1, 3]] for p in self.poses])

                    # Save to files
                    self._save_outputs(waypoints, trajectory)

                    # Send waypoints
                    wp_flat = waypoints.flatten().astype(np.float32)
                    send_output(
                        "waypoints",
                        pa.array(wp_flat, type=pa.float32()),
                        dora_event["metadata"]
                    )

                    # Send trajectory
                    traj_flat = trajectory.flatten().astype(np.float32)
                    send_output(
                        "trajectory",
                        pa.array(traj_flat, type=pa.float32()),
                        dora_event["metadata"]
                    )

                    self.waypoints_extracted = True
                    print(f"[WaypointExtractor] Extracted {len(waypoints)} waypoints from {len(self.poses)} poses")

        elif dora_event["type"] == "STOP":
            # Extract waypoints on stop if not done
            if not self.waypoints_extracted and len(self.poses) > 0:
                waypoints = self._extract_waypoints()
                trajectory = np.array([[p[0, 3], p[1, 3]] for p in self.poses])
                self._save_outputs(waypoints, trajectory)
            print(f"[WaypointExtractor] Stopped")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
