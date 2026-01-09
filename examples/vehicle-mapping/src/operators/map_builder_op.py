#!/usr/bin/env python3
"""
Map Builder Operator for DORA

Accumulates point clouds into a global map using estimated poses.

Inputs:
    - pointcloud: Point cloud data as flattened float32 array
    - pose: SE3 pose as flattened 4x4 matrix
    - sequence_complete: Signal when sequence is done

Outputs:
    - map_stats: [n_points, n_frames, map_size_mb]
    - map_complete: Signal when map is saved
"""

import os
from pathlib import Path
import numpy as np
import pyarrow as pa
from dora import DoraStatus

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False


class Operator:
    """DORA Operator for Map Builder."""

    def __init__(self):
        if not OPEN3D_AVAILABLE:
            raise ImportError("open3d is required: pip install open3d")

        # Load configuration
        config_path = Path(__file__).parent.parent.parent / 'config' / 'mapping_config.yaml'
        self.config = self._load_config(config_path)

        # Map parameters
        map_config = self.config.get('map', {})
        self.voxel_size = map_config.get('voxel_size', 0.05)
        self.downsample_interval = map_config.get('downsample_interval', 10)

        # Output directory
        self.output_dir = Path(os.environ.get(
            'MAP_OUTPUT_DIR',
            str(Path(__file__).parent.parent.parent / 'output' / 'dora_map')
        ))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # State
        self.global_map = o3d.geometry.PointCloud()
        self.frame_count = 0
        self.pending_cloud = None
        self.pending_pose = None
        self.map_saved = False

        print(f"[MapBuilder] Initialized: voxel={self.voxel_size}m, output={self.output_dir}")

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

    def _add_frame(self, points: np.ndarray, pose: np.ndarray):
        """Add a frame to the global map."""
        if len(points) == 0:
            return

        # Transform points to world frame
        R = pose[:3, :3]
        t = pose[:3, 3]
        points_world = (R @ points.T).T + t

        # Add to global map
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points_world)
        self.global_map += pcd

        self.frame_count += 1

        # Periodic downsampling to keep map manageable
        if self.frame_count % self.downsample_interval == 0:
            self.global_map = self.global_map.voxel_down_sample(self.voxel_size)

    def _save_map(self):
        """Save the final map."""
        if self.map_saved:
            return

        # Final downsampling
        self.global_map = self.global_map.voxel_down_sample(self.voxel_size)

        # Remove outliers
        self.global_map, _ = self.global_map.remove_statistical_outlier(
            nb_neighbors=20, std_ratio=2.0
        )

        # Save in multiple formats
        ply_path = self.output_dir / 'map.ply'
        pcd_path = self.output_dir / 'map.pcd'

        o3d.io.write_point_cloud(str(ply_path), self.global_map)
        o3d.io.write_point_cloud(str(pcd_path), self.global_map)

        n_points = len(self.global_map.points)
        print(f"[MapBuilder] Saved map: {n_points} points")
        print(f"[MapBuilder] Output: {ply_path}")

        self.map_saved = True

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "pointcloud":
                # Store pending point cloud
                points_flat = dora_event["value"].to_numpy()
                if len(points_flat) > 0:
                    self.pending_cloud = points_flat.reshape(-1, 3)

            elif event_id == "pose":
                # Store pending pose
                pose_flat = dora_event["value"].to_numpy()
                if len(pose_flat) == 16:
                    self.pending_pose = pose_flat.reshape(4, 4)

                # Process if we have both cloud and pose
                if self.pending_cloud is not None and self.pending_pose is not None:
                    self._add_frame(self.pending_cloud, self.pending_pose)

                    # Send map stats
                    n_points = len(self.global_map.points)
                    stats = [float(n_points), float(self.frame_count), float(n_points * 12 / 1e6)]
                    send_output(
                        "map_stats",
                        pa.array(stats, type=pa.float32()),
                        dora_event["metadata"]
                    )

                    if self.frame_count % 10 == 0:
                        print(f"[MapBuilder] Frame {self.frame_count}: {n_points} map points")

                    # Clear pending
                    self.pending_cloud = None
                    self.pending_pose = None

            elif event_id == "sequence_complete":
                # Get expected frame count from the signal
                signal = dora_event["value"].to_numpy()
                expected_frames = int(signal[0]) if len(signal) > 0 and signal[0] > 1 else 0

                # Only save if we've processed all frames or signal is just completion marker
                if expected_frames == 0 or self.frame_count >= expected_frames:
                    # Save the map
                    self._save_map()

                    # Send completion signal with frame count
                    send_output(
                        "map_complete",
                        pa.array([float(self.frame_count)], type=pa.float32()),
                        dora_event["metadata"]
                    )
                else:
                    print(f"[MapBuilder] Waiting for frames: {self.frame_count}/{expected_frames}")

        elif dora_event["type"] == "STOP":
            # Save map on stop if not already saved
            if not self.map_saved and self.frame_count > 0:
                self._save_map()
            print(f"[MapBuilder] Stopped. {self.frame_count} frames processed")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
