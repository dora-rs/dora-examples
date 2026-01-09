#!/usr/bin/env python3
"""
Waypoint Extractor - Extract waypoints from trajectory for path-following.

This module extracts 2D waypoints from optimized poses, compatible with
the vehicle-path-following example.
"""

from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np


class WaypointExtractor:
    """Extract waypoints from trajectory for path-following."""

    def __init__(self, config: dict = None):
        """
        Initialize waypoint extractor.

        Args:
            config: Configuration dictionary with optional keys:
                - min_distance: Minimum distance between waypoints (default: 0.5)
                - simplify: Whether to simplify trajectory (default: True)
                - simplify_tolerance: Douglas-Peucker tolerance (default: 0.1)
                - z_threshold: Max Z change to include waypoint (default: None)
        """
        config = config or {}

        self.min_distance = config.get('min_distance', 0.5)
        self.simplify = config.get('simplify', True)
        self.simplify_tolerance = config.get('simplify_tolerance', 0.1)
        self.z_threshold = config.get('z_threshold', None)

    def extract(self, poses: Dict[int, np.ndarray]) -> List[Tuple[float, float]]:
        """
        Extract 2D waypoints from poses.

        Args:
            poses: Dictionary of pose ID to 4x4 transformation matrix

        Returns:
            List of (x, y) waypoint tuples
        """
        if not poses:
            return []

        # Extract positions in sorted order
        sorted_ids = sorted(poses.keys())
        positions = np.array([poses[i][:3, 3] for i in sorted_ids])

        # Filter by minimum distance
        waypoints_3d = self._filter_by_distance(positions)

        # Optional: filter by Z threshold (for ground vehicles)
        if self.z_threshold is not None:
            waypoints_3d = self._filter_by_z(waypoints_3d)

        # Simplify trajectory
        if self.simplify:
            waypoints_3d = self._simplify_trajectory(waypoints_3d)

        # Extract 2D (x, y)
        waypoints = [(float(p[0]), float(p[1])) for p in waypoints_3d]

        return waypoints

    def _filter_by_distance(self, positions: np.ndarray) -> np.ndarray:
        """Filter positions by minimum distance."""
        if len(positions) == 0:
            return positions

        filtered = [positions[0]]

        for pos in positions[1:]:
            dist = np.linalg.norm(pos[:2] - filtered[-1][:2])
            if dist >= self.min_distance:
                filtered.append(pos)

        return np.array(filtered)

    def _filter_by_z(self, positions: np.ndarray) -> np.ndarray:
        """Filter out positions with large Z changes (non-ground)."""
        if len(positions) == 0:
            return positions

        z_ref = np.median(positions[:, 2])
        mask = np.abs(positions[:, 2] - z_ref) < self.z_threshold
        return positions[mask]

    def _simplify_trajectory(self, positions: np.ndarray) -> np.ndarray:
        """
        Simplify trajectory using Douglas-Peucker algorithm.

        This reduces the number of waypoints while preserving shape.
        """
        if len(positions) < 3:
            return positions

        # Use 2D for simplification
        points_2d = positions[:, :2]
        indices = self._douglas_peucker(points_2d, self.simplify_tolerance)

        return positions[indices]

    def _douglas_peucker(self, points: np.ndarray, tolerance: float) -> List[int]:
        """
        Douglas-Peucker line simplification algorithm.

        Returns indices of points to keep.
        """
        if len(points) < 3:
            return list(range(len(points)))

        # Find point with maximum distance from line between first and last
        start, end = points[0], points[-1]
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)

        if line_len < 1e-6:
            return [0, len(points) - 1]

        line_unit = line_vec / line_len

        # Distance from each point to line
        distances = []
        for i, p in enumerate(points):
            v = p - start
            proj_len = np.dot(v, line_unit)
            proj = start + proj_len * line_unit
            dist = np.linalg.norm(p - proj)
            distances.append(dist)

        max_dist = max(distances)
        max_idx = distances.index(max_dist)

        if max_dist > tolerance:
            # Recursively simplify
            left = self._douglas_peucker(points[:max_idx + 1], tolerance)
            right = self._douglas_peucker(points[max_idx:], tolerance)
            # Combine, avoiding duplicate at max_idx
            return left[:-1] + [i + max_idx for i in right]
        else:
            return [0, len(points) - 1]

    def save_waypoints(self, waypoints: List[Tuple[float, float]], output_path: str,
                       header: str = None):
        """
        Save waypoints in vehicle-path-following format.

        Args:
            waypoints: List of (x, y) tuples
            output_path: Output file path
            header: Optional header comment
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            if header:
                f.write(f"# {header}\n")
            f.write("# Waypoints extracted from mapping trajectory\n")
            f.write("# Format: x y (meters)\n")
            f.write(f"# Total waypoints: {len(waypoints)}\n\n")

            for x, y in waypoints:
                f.write(f"{x:.4f} {y:.4f}\n")

        print(f"[WaypointExtractor] Saved {len(waypoints)} waypoints to {output_path}")

    def compute_statistics(self, waypoints: List[Tuple[float, float]]) -> dict:
        """Compute waypoint statistics."""
        if not waypoints:
            return {'n_waypoints': 0}

        positions = np.array(waypoints)

        # Compute total path length
        total_length = 0
        for i in range(1, len(positions)):
            total_length += np.linalg.norm(positions[i] - positions[i - 1])

        # Average spacing
        avg_spacing = total_length / (len(positions) - 1) if len(positions) > 1 else 0

        return {
            'n_waypoints': len(waypoints),
            'total_length': total_length,
            'avg_spacing': avg_spacing,
            'bounds_min': positions.min(axis=0).tolist(),
            'bounds_max': positions.max(axis=0).tolist(),
        }


def save_trajectory(poses: Dict[int, np.ndarray], output_path: str):
    """
    Save full trajectory (3D poses) to file.

    Format: timestamp x y z qx qy qz qw
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write("# Trajectory from mapping\n")
        f.write("# Format: id x y z qx qy qz qw\n\n")

        for pose_id in sorted(poses.keys()):
            pose = poses[pose_id]
            t = pose[:3, 3]

            # Convert rotation matrix to quaternion
            R = pose[:3, :3]
            q = rotation_matrix_to_quaternion(R)

            f.write(f"{pose_id} {t[0]:.6f} {t[1]:.6f} {t[2]:.6f} "
                    f"{q[0]:.6f} {q[1]:.6f} {q[2]:.6f} {q[3]:.6f}\n")


def rotation_matrix_to_quaternion(R: np.ndarray) -> np.ndarray:
    """Convert 3x3 rotation matrix to quaternion [x, y, z, w]."""
    # Algorithm from: https://www.euclideanspace.com/maths/geometry/rotations/conversions/matrixToQuaternion/
    trace = np.trace(R)

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s

    return np.array([x, y, z, w])
