#!/usr/bin/env python3
"""
ICP Odometry Operator for DORA

Estimates robot poses from sequential point clouds using ICP.

Inputs:
    - pointcloud: Point cloud data as flattened float32 array
    - frame_info: Frame metadata [frame_idx, total_frames, n_points]

Outputs:
    - pose: SE3 pose as flattened 4x4 matrix (16 floats)
    - odometry_status: [frame_idx, fitness, rmse]
"""

import os
from pathlib import Path
from typing import List, Optional
import numpy as np
import pyarrow as pa
from dora import DoraStatus

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False


class Operator:
    """DORA Operator for ICP Odometry."""

    def __init__(self):
        if not OPEN3D_AVAILABLE:
            raise ImportError("open3d is required: pip install open3d")

        # Load configuration
        config_path = Path(__file__).parent.parent.parent / 'config' / 'mapping_config.yaml'
        self.config = self._load_config(config_path)

        # ICP parameters
        icp_config = self.config.get('icp', {})
        self.voxel_size = icp_config.get('voxel_size', 0.1)
        self.max_correspondence = icp_config.get('max_correspondence_distance', 1.0)
        self.max_iteration = icp_config.get('max_iteration', 50)

        # State
        self.poses = [np.eye(4)]  # List of SE3 poses
        self.prev_pcd = None
        self.world_clouds = []  # Point clouds in world frame for local map
        self.window_size = 5  # Sliding window for local map
        self.frame_count = 0

        print(f"[IcpOdometry] Initialized: voxel={self.voxel_size}m, correspondence={self.max_correspondence}m")

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

    def _preprocess(self, points: np.ndarray) -> o3d.geometry.PointCloud:
        """Preprocess point cloud for ICP."""
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))

        if self.voxel_size > 0:
            pcd = pcd.voxel_down_sample(self.voxel_size)

        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=self.voxel_size * 2, max_nn=30
            )
        )
        return pcd

    def _register_frame(self, points: np.ndarray) -> tuple:
        """Register current frame and return (pose, fitness, rmse)."""
        if self.frame_count == 0:
            # First frame - identity pose
            self.world_clouds.append(points.copy())
            self.frame_count += 1
            return np.eye(4), 1.0, 0.0

        # Build local map from recent frames
        start_idx = max(0, len(self.world_clouds) - self.window_size)
        local_map_points = []
        for i in range(start_idx, len(self.world_clouds)):
            pts = self.world_clouds[i]
            step = max(1, len(pts) // 5000)
            local_map_points.append(pts[::step])

        if local_map_points:
            local_map_points = np.vstack(local_map_points)
            target_pcd = self._preprocess(local_map_points)
        else:
            return self.poses[-1].copy(), 0.0, 0.0

        # Preprocess current frame
        curr_pcd = self._preprocess(points)
        curr_pts = np.asarray(curr_pcd.points)

        # Transform current frame to world using previous pose estimate
        prev_pose = self.poses[-1]
        curr_world = (prev_pose[:3, :3] @ curr_pts.T).T + prev_pose[:3, 3]

        curr_world_pcd = o3d.geometry.PointCloud()
        curr_world_pcd.points = o3d.utility.Vector3dVector(curr_world)
        curr_world_pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=self.voxel_size * 2, max_nn=30
            )
        )

        # Run ICP
        result = o3d.pipelines.registration.registration_icp(
            curr_world_pcd, target_pcd,
            self.max_correspondence * 2,
            np.eye(4),
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            o3d.pipelines.registration.ICPConvergenceCriteria(
                max_iteration=self.max_iteration * 2
            )
        )

        # Compute final pose
        T_correction = result.transformation
        T_abs = T_correction @ prev_pose

        # Validate pose jump
        delta_pos = np.linalg.norm(T_abs[:3, 3] - prev_pose[:3, 3])
        if delta_pos > 0.75:  # Expected ~0.25m per frame
            # Use motion model fallback
            if len(self.poses) >= 2:
                velocity = self.poses[-1][:3, 3] - self.poses[-2][:3, 3]
                T_abs = prev_pose.copy()
                T_abs[:3, 3] += velocity
            else:
                T_abs = prev_pose.copy()
            fitness = 0.0
        else:
            fitness = result.fitness

        # Store for next iteration
        self.poses.append(T_abs)
        curr_world_final = (T_abs[:3, :3] @ points.T).T + T_abs[:3, 3]
        self.world_clouds.append(curr_world_final)
        self.frame_count += 1

        return T_abs, fitness, result.inlier_rmse

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "pointcloud":
                # Reshape point cloud from flat array
                points_flat = dora_event["value"].to_numpy()
                if len(points_flat) == 0:
                    return DoraStatus.CONTINUE

                points = points_flat.reshape(-1, 3)

                # Register frame
                pose, fitness, rmse = self._register_frame(points)

                # Send pose (flattened 4x4 matrix)
                pose_flat = pose.flatten().astype(np.float32)
                send_output(
                    "pose",
                    pa.array(pose_flat, type=pa.float32()),
                    dora_event["metadata"]
                )

                # Send odometry status
                status = [float(self.frame_count - 1), fitness, rmse]
                send_output(
                    "odometry_status",
                    pa.array(status, type=pa.float32()),
                    dora_event["metadata"]
                )

                if self.frame_count % 5 == 0:
                    pos = pose[:3, 3]
                    print(f"[IcpOdometry] Frame {self.frame_count}: pos=({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}), fitness={fitness:.3f}")

            elif event_id == "frame_info":
                # Frame info received - could use for synchronization
                pass

        elif dora_event["type"] == "STOP":
            print(f"[IcpOdometry] Stopped. Processed {self.frame_count} frames")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
