#!/usr/bin/env python3
"""
KISS-ICP Runner - Wrapper for KISS-ICP odometry.

KISS-ICP is a LiDAR odometry pipeline that uses point-to-point ICP
with adaptive thresholding for robust frame-to-frame registration.

Installation:
    pip install kiss-icp

References:
    - https://github.com/PRBonn/kiss-icp
    - https://pypi.org/project/kiss-icp/
"""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import numpy as np

try:
    from kiss_icp.pipeline import OdometryPipeline
    from kiss_icp.config import KISSConfig
    KISS_ICP_AVAILABLE = True
except ImportError:
    KISS_ICP_AVAILABLE = False
    print("Warning: kiss-icp not installed. Install with: pip install kiss-icp")


class KissICPRunner:
    """Wrapper for KISS-ICP odometry."""

    def __init__(self, config: dict = None):
        """
        Initialize KISS-ICP runner.

        Args:
            config: Configuration dictionary with optional keys:
                - max_range: Maximum point range (default: 100.0)
                - min_range: Minimum point range (default: 0.5)
                - voxel_size: Voxel size for downsampling (default: 0.5)
                - max_points_per_voxel: Max points per voxel (default: 20)
        """
        self.config = config or {}
        self.max_range = self.config.get('max_range', 100.0)
        self.min_range = self.config.get('min_range', 0.5)
        self.voxel_size = self.config.get('voxel_size', 0.5)

        self.poses = []
        self.pipeline = None

    def _create_kiss_config(self) -> 'KISSConfig':
        """Create KISS-ICP configuration."""
        if not KISS_ICP_AVAILABLE:
            raise ImportError("kiss-icp not installed")

        config = KISSConfig()
        config.data.max_range = self.max_range
        config.data.min_range = self.min_range
        config.mapping.voxel_size = self.voxel_size
        return config

    def run_on_sequence(self, point_clouds: List[np.ndarray]) -> np.ndarray:
        """
        Run KISS-ICP on a sequence of point clouds.

        Args:
            point_clouds: List of Nx3 numpy arrays

        Returns:
            Mx4x4 array of SE3 poses (M = number of frames)
        """
        if not KISS_ICP_AVAILABLE:
            raise ImportError("kiss-icp not installed. Run: pip install kiss-icp")

        from kiss_icp.kiss_icp import KissICP

        # Initialize KISS-ICP
        config = self._create_kiss_config()
        kiss_icp = KissICP(config)

        poses = []
        for i, points in enumerate(point_clouds):
            # Ensure points are float64
            points = points.astype(np.float64)

            # Create dummy timestamps (required by KISS-ICP preprocessor)
            # Timestamps are used for motion compensation in spinning LiDARs
            timestamps = np.zeros(len(points), dtype=np.float64)

            # Register frame
            kiss_icp.register_frame(points, timestamps=timestamps)

            # Get current pose
            pose = kiss_icp.poses[-1]
            poses.append(pose)

        return np.array(poses)

    def run_cli(self, data_dir: str, output_dir: str = None,
                visualize: bool = False) -> Path:
        """
        Run KISS-ICP using command line interface.

        Args:
            data_dir: Directory containing point cloud files
            output_dir: Output directory (default: data_dir/results)
            visualize: Whether to show visualization

        Returns:
            Path to output directory
        """
        data_path = Path(data_dir)
        if output_dir:
            out_path = Path(output_dir)
        else:
            out_path = data_path / "kiss_icp_results"

        cmd = ["kiss_icp_pipeline", str(data_path)]

        if not visualize:
            cmd.append("--no-visualize")

        cmd.extend(["--output", str(out_path)])

        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"KISS-ICP error: {result.stderr}")
            raise RuntimeError("KISS-ICP failed")

        print(result.stdout)
        return out_path

    def load_poses_from_file(self, poses_file: Path) -> np.ndarray:
        """
        Load poses from KISS-ICP output file.

        Args:
            poses_file: Path to poses.npy or poses.txt

        Returns:
            Nx4x4 array of poses
        """
        poses_file = Path(poses_file)

        if poses_file.suffix == '.npy':
            poses = np.load(str(poses_file))
        elif poses_file.suffix == '.txt':
            # KITTI format: 12 values per line (3x4 matrix flattened)
            data = np.loadtxt(str(poses_file))
            n_poses = len(data)
            poses = np.zeros((n_poses, 4, 4))
            for i, row in enumerate(data):
                poses[i, :3, :4] = row.reshape(3, 4)
                poses[i, 3, 3] = 1.0
        else:
            raise ValueError(f"Unknown pose file format: {poses_file.suffix}")

        return poses

    @staticmethod
    def compute_relative_pose(pose_from: np.ndarray, pose_to: np.ndarray) -> np.ndarray:
        """
        Compute relative pose between two absolute poses.

        Args:
            pose_from: 4x4 SE3 matrix (source)
            pose_to: 4x4 SE3 matrix (target)

        Returns:
            4x4 relative transformation from pose_from to pose_to
        """
        return np.linalg.inv(pose_from) @ pose_to

    @staticmethod
    def save_poses(poses: np.ndarray, output_path: str, format: str = 'kitti'):
        """
        Save poses to file.

        Args:
            poses: Nx4x4 array of poses
            output_path: Output file path
            format: 'kitti' (txt) or 'numpy' (npy)
        """
        output_path = Path(output_path)

        if format == 'numpy':
            np.save(str(output_path.with_suffix('.npy')), poses)
        elif format == 'kitti':
            with open(output_path.with_suffix('.txt'), 'w') as f:
                for pose in poses:
                    # KITTI format: 12 values (3x4 matrix flattened)
                    row = pose[:3, :4].flatten()
                    f.write(' '.join(f'{v:.6e}' for v in row) + '\n')
        else:
            raise ValueError(f"Unknown format: {format}")


def run_kiss_icp_simple(data_dir: str, config: dict = None) -> np.ndarray:
    """
    Simple wrapper to run KISS-ICP on a directory of point clouds.

    Args:
        data_dir: Directory containing PCD/PLY/BIN files
        config: Optional configuration

    Returns:
        Nx4x4 array of poses
    """
    from .pcd_loader import PCDLoader

    # Load point clouds
    loader = PCDLoader(data_dir, config)
    _, point_clouds = loader.load_sequence(preprocess=False)

    # Run KISS-ICP
    runner = KissICPRunner(config)
    poses = runner.run_on_sequence(point_clouds)

    return poses


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run KISS-ICP odometry")
    parser.add_argument("data_dir", help="Directory containing PCD files")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--visualize", "-v", action="store_true")
    args = parser.parse_args()

    runner = KissICPRunner()
    output = runner.run_cli(args.data_dir, args.output, args.visualize)
    print(f"Results saved to: {output}")
