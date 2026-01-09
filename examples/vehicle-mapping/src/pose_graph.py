#!/usr/bin/env python3
"""
Pose Graph Optimizer - GTSAM-based pose graph optimization.

This module builds a factor graph from odometry constraints and
optimizes it using GTSAM's nonlinear optimization.

Installation:
    conda install -c conda-forge gtsam
    # Or build from source: https://github.com/borglab/gtsam

References:
    - https://gtsam.org/
    - https://github.com/borglab/gtsam
"""

from typing import Dict, List, Tuple, Optional
import numpy as np

try:
    import gtsam
    from gtsam import Pose3, Rot3
    GTSAM_AVAILABLE = True
except ImportError:
    GTSAM_AVAILABLE = False
    print("Warning: gtsam not installed. Install with: conda install -c conda-forge gtsam")


def matrix_to_pose3(matrix: np.ndarray) -> 'Pose3':
    """Convert 4x4 numpy matrix to GTSAM Pose3."""
    if not GTSAM_AVAILABLE:
        raise ImportError("gtsam not installed")

    R = Rot3(matrix[:3, :3])
    t = matrix[:3, 3]
    return Pose3(R, t)


def pose3_to_matrix(pose: 'Pose3') -> np.ndarray:
    """Convert GTSAM Pose3 to 4x4 numpy matrix."""
    return pose.matrix()


class PoseGraphOptimizer:
    """GTSAM-based pose graph optimization."""

    def __init__(self, config: dict = None):
        """
        Initialize pose graph optimizer.

        Args:
            config: Configuration dictionary with optional keys:
                - odom_noise: Odometry noise [rx, ry, rz, tx, ty, tz]
                - loop_noise: Loop closure noise
                - prior_noise: Prior factor noise
        """
        if not GTSAM_AVAILABLE:
            raise ImportError("gtsam not installed. Install with: conda install -c conda-forge gtsam")

        config = config or {}

        # Noise models (rotation then translation, in radians and meters)
        odom_noise = config.get('odom_noise', {})
        odom_rot = odom_noise.get('rotation', [0.1, 0.1, 0.1])
        odom_trans = odom_noise.get('translation', [0.05, 0.05, 0.05])

        loop_noise = config.get('loop_noise', {})
        loop_rot = loop_noise.get('rotation', [0.2, 0.2, 0.2])
        loop_trans = loop_noise.get('translation', [0.1, 0.1, 0.1])

        prior_noise = config.get('prior_noise', [0.01, 0.01, 0.01, 0.01, 0.01, 0.01])

        # Create noise models
        self.noise_model_odom = gtsam.noiseModel.Diagonal.Sigmas(
            np.array(odom_rot + odom_trans)
        )
        self.noise_model_loop = gtsam.noiseModel.Diagonal.Sigmas(
            np.array(loop_rot + loop_trans)
        )
        self.noise_model_prior = gtsam.noiseModel.Diagonal.Sigmas(
            np.array(prior_noise)
        )

        # Factor graph and initial estimates
        self.graph = gtsam.NonlinearFactorGraph()
        self.initial_estimates = gtsam.Values()

        # Track added poses
        self.pose_ids = set()
        self.n_odom_factors = 0
        self.n_loop_factors = 0

    def add_prior(self, pose_id: int, pose: np.ndarray):
        """
        Add prior factor for a pose (typically the first pose).

        Args:
            pose_id: Pose identifier
            pose: 4x4 SE3 transformation matrix
        """
        pose3 = matrix_to_pose3(pose)
        self.graph.add(gtsam.PriorFactorPose3(
            pose_id,
            pose3,
            self.noise_model_prior
        ))

    def add_initial_estimate(self, pose_id: int, pose: np.ndarray):
        """
        Add initial pose estimate.

        Args:
            pose_id: Pose identifier
            pose: 4x4 SE3 transformation matrix
        """
        if pose_id not in self.pose_ids:
            pose3 = matrix_to_pose3(pose)
            self.initial_estimates.insert(pose_id, pose3)
            self.pose_ids.add(pose_id)

    def add_odometry_factor(self, id_from: int, id_to: int,
                            relative_pose: np.ndarray):
        """
        Add odometry (between) factor.

        Args:
            id_from: Source pose ID
            id_to: Target pose ID
            relative_pose: 4x4 relative transformation from id_from to id_to
        """
        pose3 = matrix_to_pose3(relative_pose)
        self.graph.add(gtsam.BetweenFactorPose3(
            id_from, id_to,
            pose3,
            self.noise_model_odom
        ))
        self.n_odom_factors += 1

    def add_loop_closure(self, id_from: int, id_to: int,
                         relative_pose: np.ndarray):
        """
        Add loop closure constraint.

        Args:
            id_from: Source pose ID
            id_to: Target pose ID
            relative_pose: 4x4 relative transformation
        """
        pose3 = matrix_to_pose3(relative_pose)
        self.graph.add(gtsam.BetweenFactorPose3(
            id_from, id_to,
            pose3,
            self.noise_model_loop
        ))
        self.n_loop_factors += 1

    def optimize(self, max_iterations: int = 100) -> Dict[int, np.ndarray]:
        """
        Run optimization and return optimized poses.

        Args:
            max_iterations: Maximum optimization iterations

        Returns:
            Dictionary mapping pose ID to 4x4 transformation matrix
        """
        # Configure optimizer
        params = gtsam.LevenbergMarquardtParams()
        params.setMaxIterations(max_iterations)
        params.setVerbosity("ERROR")

        # Run optimization
        optimizer = gtsam.LevenbergMarquardtOptimizer(
            self.graph, self.initial_estimates, params
        )
        result = optimizer.optimize()

        # Extract optimized poses
        optimized_poses = {}
        for pose_id in self.pose_ids:
            pose3 = result.atPose3(pose_id)
            optimized_poses[pose_id] = pose3_to_matrix(pose3)

        return optimized_poses

    def build_from_odometry(self, odom_poses: np.ndarray) -> Dict[int, np.ndarray]:
        """
        Build pose graph from odometry chain and optimize.

        This creates a chain of between factors connecting consecutive poses.

        Args:
            odom_poses: Nx4x4 array of absolute poses from odometry

        Returns:
            Dictionary of optimized poses
        """
        n_poses = len(odom_poses)
        if n_poses == 0:
            return {}

        # Add prior on first pose
        self.add_prior(0, odom_poses[0])
        self.add_initial_estimate(0, odom_poses[0])

        # Add odometry chain
        for i in range(1, n_poses):
            # Compute relative pose between consecutive frames
            T_prev = odom_poses[i - 1]
            T_curr = odom_poses[i]
            T_rel = np.linalg.inv(T_prev) @ T_curr

            self.add_odometry_factor(i - 1, i, T_rel)
            self.add_initial_estimate(i, odom_poses[i])

        # Optimize
        return self.optimize()

    def get_statistics(self) -> dict:
        """Get optimization statistics."""
        return {
            'n_poses': len(self.pose_ids),
            'n_odom_factors': self.n_odom_factors,
            'n_loop_factors': self.n_loop_factors,
            'n_total_factors': self.graph.size()
        }


def compute_trajectory_length(poses: Dict[int, np.ndarray]) -> float:
    """Compute total trajectory length from poses."""
    length = 0.0
    sorted_ids = sorted(poses.keys())

    for i in range(1, len(sorted_ids)):
        p1 = poses[sorted_ids[i - 1]][:3, 3]
        p2 = poses[sorted_ids[i]][:3, 3]
        length += np.linalg.norm(p2 - p1)

    return length


def save_poses_tum(poses: Dict[int, np.ndarray], output_path: str,
                   timestamps: List[float] = None):
    """
    Save poses in TUM format.

    TUM format: timestamp tx ty tz qx qy qz qw

    Args:
        poses: Dictionary of pose ID to 4x4 matrix
        output_path: Output file path
        timestamps: Optional timestamps (uses pose IDs if not provided)
    """
    if not GTSAM_AVAILABLE:
        raise ImportError("gtsam required for quaternion conversion")

    with open(output_path, 'w') as f:
        for i, pose_id in enumerate(sorted(poses.keys())):
            pose = poses[pose_id]
            t = pose[:3, 3]

            # Convert rotation to quaternion
            pose3 = matrix_to_pose3(pose)
            q = pose3.rotation().toQuaternion()

            ts = timestamps[i] if timestamps else float(pose_id)
            f.write(f"{ts:.6f} {t[0]:.6f} {t[1]:.6f} {t[2]:.6f} "
                    f"{q.x():.6f} {q.y():.6f} {q.z():.6f} {q.w():.6f}\n")


if __name__ == "__main__":
    # Simple test
    print("Testing PoseGraphOptimizer...")

    # Create synthetic odometry
    n_poses = 10
    poses = np.zeros((n_poses, 4, 4))
    for i in range(n_poses):
        poses[i] = np.eye(4)
        poses[i, 0, 3] = i * 1.0  # Move along X

    # Add some noise
    poses[5:, 0, 3] += 0.1  # Drift

    # Optimize
    optimizer = PoseGraphOptimizer()
    optimized = optimizer.build_from_odometry(poses)

    print(f"Optimized {len(optimized)} poses")
    print(f"Stats: {optimizer.get_statistics()}")
