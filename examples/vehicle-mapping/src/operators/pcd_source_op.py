#!/usr/bin/env python3
"""
PCD Source Operator for DORA

Reads PCD files from a directory and publishes point clouds.

Inputs:
    - tick: Timer trigger for publishing

Outputs:
    - pointcloud: Point cloud data as flattened float32 array [x1,y1,z1, x2,y2,z2, ...]
    - frame_info: Frame metadata [frame_idx, total_frames, timestamp]
    - sequence_complete: Signal when all frames have been published
"""

import os
import json
from pathlib import Path
from typing import List
import numpy as np
import pyarrow as pa
from dora import DoraStatus

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False


class Operator:
    """DORA Operator for PCD file source."""

    def __init__(self):
        if not OPEN3D_AVAILABLE:
            raise ImportError("open3d is required: pip install open3d")

        # Get data directory from environment or use default
        self.data_dir = os.environ.get(
            'PCD_DATA_DIR',
            str(Path(__file__).parent.parent.parent / 'data' / 'rectangle_sequence')
        )

        # Load configuration
        config_path = Path(__file__).parent.parent.parent / 'config' / 'mapping_config.yaml'
        self.config = self._load_config(config_path)

        # Find PCD files
        self.pcd_files = self._find_pcd_files()
        self.current_frame = 0
        self.sequence_complete_sent = False

        # Preprocessing parameters
        loader_config = self.config.get('loader', {})
        self.voxel_size = loader_config.get('voxel_size', 0.1)
        self.min_range = loader_config.get('min_range', 0.5)
        self.max_range = loader_config.get('max_range', 50.0)

        print(f"[PcdSource] Data directory: {self.data_dir}")
        print(f"[PcdSource] Found {len(self.pcd_files)} PCD files")
        print(f"[PcdSource] Voxel size: {self.voxel_size}m, Range: [{self.min_range}, {self.max_range}]m")

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

    def _find_pcd_files(self) -> List[Path]:
        """Find all PCD files in data directory."""
        data_path = Path(self.data_dir)
        if not data_path.exists():
            print(f"[PcdSource] Warning: Data directory not found: {self.data_dir}")
            return []

        pcd_files = sorted(data_path.glob("*.pcd"))
        return pcd_files

    def _load_and_preprocess(self, pcd_path: Path) -> np.ndarray:
        """Load and preprocess a PCD file."""
        # Load PCD
        pcd = o3d.io.read_point_cloud(str(pcd_path))
        points = np.asarray(pcd.points).astype(np.float32)

        if len(points) == 0:
            return np.zeros((0, 3), dtype=np.float32)

        # Range filtering
        distances = np.linalg.norm(points, axis=1)
        mask = (distances >= self.min_range) & (distances <= self.max_range)
        points = points[mask]

        # Voxel downsampling
        if self.voxel_size > 0 and len(points) > 0:
            pcd_filtered = o3d.geometry.PointCloud()
            pcd_filtered.points = o3d.utility.Vector3dVector(points)
            pcd_down = pcd_filtered.voxel_down_sample(self.voxel_size)
            points = np.asarray(pcd_down.points).astype(np.float32)

        return points

    def on_event(self, dora_event, send_output) -> str:
        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "tick":
                if self.current_frame < len(self.pcd_files):
                    # Load and publish point cloud
                    pcd_path = self.pcd_files[self.current_frame]
                    points = self._load_and_preprocess(pcd_path)

                    # Flatten points for transmission [x1,y1,z1, x2,y2,z2, ...]
                    points_flat = points.flatten()

                    # Send point cloud
                    send_output(
                        "pointcloud",
                        pa.array(points_flat, type=pa.float32()),
                        dora_event["metadata"]
                    )

                    # Send frame info [frame_idx, total_frames, n_points]
                    frame_info = [
                        float(self.current_frame),
                        float(len(self.pcd_files)),
                        float(len(points))
                    ]
                    send_output(
                        "frame_info",
                        pa.array(frame_info, type=pa.float32()),
                        dora_event["metadata"]
                    )

                    if self.current_frame % 5 == 0:
                        print(f"[PcdSource] Frame {self.current_frame}/{len(self.pcd_files)}: {len(points)} points")

                    self.current_frame += 1

                elif not self.sequence_complete_sent:
                    # Signal sequence complete with total frame count
                    send_output(
                        "sequence_complete",
                        pa.array([float(len(self.pcd_files))], type=pa.float32()),
                        dora_event["metadata"]
                    )
                    self.sequence_complete_sent = True
                    print(f"[PcdSource] Sequence complete: {len(self.pcd_files)} frames")

        elif dora_event["type"] == "STOP":
            print("[PcdSource] Stopped")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
