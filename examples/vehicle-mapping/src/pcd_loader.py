#!/usr/bin/env python3
"""
PCD Loader - Load and preprocess PCD sequences from 32-line LiDAR.

This module handles loading point cloud data from PCD files,
with preprocessing options for range filtering and downsampling.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np

try:
    import open3d as o3d
except ImportError:
    raise ImportError("Please install open3d: pip install open3d")


class PCDLoader:
    """Load and preprocess PCD sequences from 32-line LiDAR."""

    def __init__(self, data_dir: str, config: dict = None):
        """
        Initialize PCD loader.

        Args:
            data_dir: Directory containing PCD files
            config: Configuration dictionary with optional keys:
                - voxel_size: Preprocessing voxel size (default: 0.1)
                - max_range: Maximum LiDAR range in meters (default: 100.0)
                - min_range: Minimum LiDAR range in meters (default: 0.5)
                - remove_ground: Whether to remove ground points (default: False)
                - ground_threshold: Ground removal threshold (default: -1.5)
        """
        self.data_dir = Path(data_dir)
        config = config or {}

        self.voxel_size = config.get('voxel_size', 0.1)
        self.max_range = config.get('max_range', 100.0)
        self.min_range = config.get('min_range', 0.5)
        self.remove_ground = config.get('remove_ground', False)
        self.ground_threshold = config.get('ground_threshold', -1.5)

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

    def get_pcd_files(self) -> List[Path]:
        """Get sorted list of PCD files in directory."""
        pcd_files = sorted(self.data_dir.glob("*.pcd"))
        if not pcd_files:
            raise FileNotFoundError(f"No PCD files found in {self.data_dir}")
        return pcd_files

    def load_pcd(self, file_path: Path) -> np.ndarray:
        """
        Load a single PCD file.

        Args:
            file_path: Path to PCD file

        Returns:
            Nx3 numpy array of points
        """
        pcd = o3d.io.read_point_cloud(str(file_path))
        points = np.asarray(pcd.points)
        return points

    def preprocess(self, points: np.ndarray) -> np.ndarray:
        """
        Preprocess point cloud.

        Args:
            points: Nx3 numpy array of points

        Returns:
            Preprocessed Nx3 numpy array
        """
        if len(points) == 0:
            return points

        # Range filter
        distances = np.linalg.norm(points, axis=1)
        mask = (distances >= self.min_range) & (distances <= self.max_range)
        points = points[mask]

        # Ground removal (simple height threshold)
        if self.remove_ground and len(points) > 0:
            mask = points[:, 2] > self.ground_threshold
            points = points[mask]

        # Voxel downsampling
        if self.voxel_size > 0 and len(points) > 0:
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(points)
            pcd = pcd.voxel_down_sample(self.voxel_size)
            points = np.asarray(pcd.points)

        return points

    def load_sequence(self, preprocess: bool = True) -> Tuple[List[Path], List[np.ndarray]]:
        """
        Load all PCD files in sequence order.

        Args:
            preprocess: Whether to preprocess point clouds

        Returns:
            Tuple of (file_paths, point_clouds)
        """
        pcd_files = self.get_pcd_files()
        point_clouds = []

        for file_path in pcd_files:
            points = self.load_pcd(file_path)
            if preprocess:
                points = self.preprocess(points)
            point_clouds.append(points)

        return pcd_files, point_clouds

    def load_frame(self, index: int, preprocess: bool = True) -> Tuple[Path, np.ndarray]:
        """
        Load a single frame by index.

        Args:
            index: Frame index
            preprocess: Whether to preprocess

        Returns:
            Tuple of (file_path, points)
        """
        pcd_files = self.get_pcd_files()
        if index < 0 or index >= len(pcd_files):
            raise IndexError(f"Frame index {index} out of range [0, {len(pcd_files)})")

        file_path = pcd_files[index]
        points = self.load_pcd(file_path)
        if preprocess:
            points = self.preprocess(points)

        return file_path, points

    def __len__(self) -> int:
        """Return number of PCD files."""
        return len(self.get_pcd_files())

    def __iter__(self):
        """Iterate over all frames."""
        pcd_files = self.get_pcd_files()
        for file_path in pcd_files:
            points = self.load_pcd(file_path)
            points = self.preprocess(points)
            yield file_path, points


def extract_timestamp_from_filename(filename: str) -> Optional[float]:
    """
    Extract timestamp from PCD filename.

    Supports formats:
    - 000001.pcd -> 1
    - 1704000000.123456.pcd -> 1704000000.123456
    - frame_001.pcd -> 1
    """
    stem = Path(filename).stem

    # Try numeric format
    try:
        return float(stem)
    except ValueError:
        pass

    # Try extracting numbers
    import re
    numbers = re.findall(r'\d+\.?\d*', stem)
    if numbers:
        return float(numbers[-1])

    return None
