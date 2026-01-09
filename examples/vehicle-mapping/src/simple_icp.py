#!/usr/bin/env python3
"""
Simple ICP Odometry - Using Open3D for point cloud registration.

This is a fallback when KISS-ICP is not available or has issues.
"""

from typing import List, Dict
import numpy as np

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False


class SimpleICPOdometry:
    """Simple frame-to-frame ICP odometry using Open3D."""

    def __init__(self, config: dict = None):
        """
        Initialize ICP odometry.

        Args:
            config: Configuration dictionary with optional keys:
                - voxel_size: Voxel size for downsampling (default: 0.1)
                - max_correspondence_distance: ICP threshold (default: 0.5)
                - max_iteration: Max ICP iterations (default: 50)
        """
        if not OPEN3D_AVAILABLE:
            raise ImportError("open3d not installed")

        config = config or {}
        self.voxel_size = config.get('voxel_size', 0.1)
        self.max_correspondence = config.get('max_correspondence_distance', 0.5)
        self.max_iteration = config.get('max_iteration', 50)

    def preprocess(self, points: np.ndarray) -> o3d.geometry.PointCloud:
        """Preprocess point cloud."""
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))

        # Voxel downsample
        if self.voxel_size > 0:
            pcd = pcd.voxel_down_sample(self.voxel_size)

        # Estimate normals for point-to-plane ICP
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=self.voxel_size * 2, max_nn=30
            )
        )

        return pcd

    def register_pair(self, source: o3d.geometry.PointCloud,
                      target: o3d.geometry.PointCloud,
                      init_transform: np.ndarray = None) -> tuple:
        """
        Register source to target point cloud.

        Returns:
            (transformation, fitness, rmse)
        """
        if init_transform is None:
            init_transform = np.eye(4)

        # Run ICP
        result = o3d.pipelines.registration.registration_icp(
            source, target,
            self.max_correspondence,
            init_transform,
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            o3d.pipelines.registration.ICPConvergenceCriteria(
                max_iteration=self.max_iteration
            )
        )

        return result.transformation, result.fitness, result.inlier_rmse

    def run_on_sequence(self, point_clouds: List[np.ndarray],
                        verbose: bool = True, use_local_map: bool = True,
                        window_size: int = 5) -> np.ndarray:
        """
        Run ICP odometry on sequence using local map for robustness.

        Args:
            point_clouds: List of Nx3 point clouds
            verbose: Print progress
            use_local_map: Use sliding window local map instead of frame-to-frame
            window_size: Number of frames to include in local map

        Returns:
            Nx4x4 array of absolute poses
        """
        n_frames = len(point_clouds)
        if n_frames == 0:
            return np.array([])

        # Initialize poses
        poses = [np.eye(4)]  # First pose is identity

        # Keep track of processed point clouds in world frame
        world_clouds = [point_clouds[0].copy()]

        for i in range(1, n_frames):
            # Build local map from recent frames (transformed to world frame)
            start_idx = max(0, i - window_size)

            if use_local_map and i > 1:
                # Combine recent point clouds into local map
                local_map_points = []
                for j in range(start_idx, i):
                    # Transform points from frame j to world frame
                    pts_world = world_clouds[j]
                    # Subsample to avoid too many points
                    step = max(1, len(pts_world) // 5000)
                    local_map_points.append(pts_world[::step])
                local_map_points = np.vstack(local_map_points)

                # Create target point cloud
                target_pcd = self.preprocess(local_map_points)
            else:
                # Frame-to-frame for first few frames
                target_pcd = self.preprocess(world_clouds[i-1])

            # Current frame in sensor coordinates
            curr_pcd = self.preprocess(point_clouds[i])

            # Use previous pose as initial guess for current pose
            init_transform = poses[-1].copy()

            # Transform current frame to world for registration
            # We register curr (in world frame estimate) to local map (in world)
            curr_world_estimate = o3d.geometry.PointCloud()
            curr_pts = np.asarray(curr_pcd.points)
            # Apply estimated pose to get world coordinates
            curr_world = (poses[-1][:3, :3] @ curr_pts.T).T + poses[-1][:3, 3]
            curr_world_estimate.points = o3d.utility.Vector3dVector(curr_world)
            curr_world_estimate.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(
                    radius=self.voxel_size * 2, max_nn=30
                )
            )

            # Register with relaxed parameters for robustness
            result = o3d.pipelines.registration.registration_icp(
                curr_world_estimate, target_pcd,
                self.max_correspondence * 2,  # Larger threshold for robustness
                np.eye(4),  # Already in world frame
                o3d.pipelines.registration.TransformationEstimationPointToPlane(),
                o3d.pipelines.registration.ICPConvergenceCriteria(
                    max_iteration=self.max_iteration * 2
                )
            )

            fitness = result.fitness
            T_correction = result.transformation

            # Apply correction to estimated pose
            T_abs = T_correction @ poses[-1]

            # Validate: check if pose changed too much (potential ICP failure)
            delta_pos = np.linalg.norm(T_abs[:3, 3] - poses[-1][:3, 3])
            expected_motion = 0.25  # Approximate motion per frame
            if delta_pos > expected_motion * 3:
                # ICP might have failed, use motion model
                if verbose:
                    print(f"  Frame {i}: Large jump detected ({delta_pos:.2f}m), using motion model")
                # Simple motion model: continue with same velocity
                if len(poses) >= 2:
                    velocity = poses[-1][:3, 3] - poses[-2][:3, 3]
                    T_abs = poses[-1].copy()
                    T_abs[:3, 3] += velocity
                else:
                    T_abs = poses[-1].copy()
                fitness = 0.0

            poses.append(T_abs)

            # Store transformed points for local map
            curr_pts_orig = np.asarray(point_clouds[i])
            curr_world_final = (T_abs[:3, :3] @ curr_pts_orig.T).T + T_abs[:3, 3]
            world_clouds.append(curr_world_final)

            if verbose and i % 5 == 0:
                pos = T_abs[:3, 3]
                print(f"  Frame {i}/{n_frames}: pos=({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}), fitness={fitness:.3f}")

        return np.array(poses)


def run_simple_icp(data_dir: str, config: dict = None) -> np.ndarray:
    """
    Run simple ICP odometry on a directory of point clouds.

    Args:
        data_dir: Directory containing PCD files
        config: Optional configuration

    Returns:
        Nx4x4 array of poses
    """
    from .pcd_loader import PCDLoader

    # Load point clouds
    loader = PCDLoader(data_dir, config)
    _, point_clouds = loader.load_sequence(preprocess=True)

    # Run ICP
    icp = SimpleICPOdometry(config)
    poses = icp.run_on_sequence(point_clouds)

    return poses
