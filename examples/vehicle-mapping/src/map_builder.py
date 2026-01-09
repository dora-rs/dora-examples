#!/usr/bin/env python3
"""
Map Builder - Build and fuse point cloud maps using Open3D.

This module transforms individual point cloud frames into a global
coordinate system and merges them into a single map.
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False
    print("Warning: open3d not installed. Install with: pip install open3d")


class MapBuilder:
    """Build and fuse point cloud map from frames."""

    def __init__(self, config: dict = None):
        """
        Initialize map builder.

        Args:
            config: Configuration dictionary with optional keys:
                - voxel_size: Frame voxel size for downsampling (default: 0.1)
                - map_voxel_size: Final map voxel size (default: 0.05)
                - remove_statistical_outliers: Remove outliers (default: True)
                - nb_neighbors: Neighbors for outlier removal (default: 20)
                - std_ratio: Std ratio for outlier removal (default: 2.0)
        """
        if not OPEN3D_AVAILABLE:
            raise ImportError("open3d not installed. Install with: pip install open3d")

        config = config or {}

        self.voxel_size = config.get('voxel_size', 0.1)
        self.map_voxel_size = config.get('map_voxel_size', 0.05)
        self.remove_outliers = config.get('remove_statistical_outliers', True)
        self.nb_neighbors = config.get('nb_neighbors', 20)
        self.std_ratio = config.get('std_ratio', 2.0)

        # Global map
        self.global_map = o3d.geometry.PointCloud()
        self.n_frames_added = 0

    def add_frame(self, points: np.ndarray, pose: np.ndarray,
                  downsample: bool = True):
        """
        Transform and add frame to global map.

        Args:
            points: Nx3 point cloud in local frame
            pose: 4x4 transformation matrix (local to global)
            downsample: Whether to downsample before adding
        """
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))

        # Downsample frame
        if downsample and self.voxel_size > 0:
            pcd = pcd.voxel_down_sample(self.voxel_size)

        # Transform to global frame
        pcd.transform(pose)

        # Merge with global map
        self.global_map += pcd
        self.n_frames_added += 1

    def build_map(self, point_clouds: List[np.ndarray],
                  poses: Dict[int, np.ndarray],
                  progress_callback=None) -> o3d.geometry.PointCloud:
        """
        Build complete map from all frames.

        Args:
            point_clouds: List of Nx3 point clouds
            poses: Dictionary mapping frame index to 4x4 pose
            progress_callback: Optional callback(current, total)

        Returns:
            Merged and downsampled point cloud map
        """
        n_frames = len(point_clouds)

        for i, cloud in enumerate(point_clouds):
            if i in poses:
                self.add_frame(cloud, poses[i])

                if progress_callback:
                    progress_callback(i + 1, n_frames)

        # Final processing
        self.finalize_map()

        return self.global_map

    def finalize_map(self):
        """Apply final processing to the map."""
        # Voxel downsample
        if self.map_voxel_size > 0:
            self.global_map = self.global_map.voxel_down_sample(self.map_voxel_size)

        # Remove statistical outliers
        if self.remove_outliers and len(self.global_map.points) > 0:
            self.global_map, _ = self.global_map.remove_statistical_outlier(
                nb_neighbors=self.nb_neighbors,
                std_ratio=self.std_ratio
            )

    def estimate_normals(self, radius: float = 0.2, max_nn: int = 30):
        """
        Estimate normals for the map.

        Args:
            radius: Search radius for normal estimation
            max_nn: Maximum neighbors for normal estimation
        """
        self.global_map.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=radius, max_nn=max_nn
            )
        )

    def save_map(self, output_path: str, estimate_normals: bool = False):
        """
        Save map to file.

        Args:
            output_path: Output file path (.ply, .pcd, .xyz, etc.)
            estimate_normals: Estimate normals before saving
        """
        if estimate_normals and not self.global_map.has_normals():
            self.estimate_normals()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        success = o3d.io.write_point_cloud(str(output_path), self.global_map)
        if success:
            print(f"[MapBuilder] Saved map to {output_path} ({len(self.global_map.points)} points)")
        else:
            print(f"[MapBuilder] Failed to save map to {output_path}")

        return success

    def get_statistics(self) -> dict:
        """Get map statistics."""
        points = np.asarray(self.global_map.points)

        if len(points) == 0:
            return {'n_points': 0}

        return {
            'n_points': len(points),
            'n_frames': self.n_frames_added,
            'bounds_min': points.min(axis=0).tolist(),
            'bounds_max': points.max(axis=0).tolist(),
            'center': points.mean(axis=0).tolist(),
        }

    def visualize(self, window_name: str = "Map"):
        """Visualize the map."""
        if len(self.global_map.points) == 0:
            print("[MapBuilder] No points to visualize")
            return

        # Add colors if not present
        if not self.global_map.has_colors():
            # Color by height
            points = np.asarray(self.global_map.points)
            z = points[:, 2]
            z_norm = (z - z.min()) / (z.max() - z.min() + 1e-6)
            colors = np.zeros((len(points), 3))
            colors[:, 0] = z_norm  # Red channel based on height
            colors[:, 2] = 1 - z_norm  # Blue channel
            self.global_map.colors = o3d.utility.Vector3dVector(colors)

        o3d.visualization.draw_geometries(
            [self.global_map],
            window_name=window_name,
            width=1280,
            height=720
        )


def load_map(file_path: str) -> o3d.geometry.PointCloud:
    """Load a point cloud map from file."""
    if not OPEN3D_AVAILABLE:
        raise ImportError("open3d not installed")

    pcd = o3d.io.read_point_cloud(file_path)
    print(f"Loaded map with {len(pcd.points)} points from {file_path}")
    return pcd


def crop_map(pcd: o3d.geometry.PointCloud,
             min_bound: List[float],
             max_bound: List[float]) -> o3d.geometry.PointCloud:
    """Crop map to bounding box."""
    bbox = o3d.geometry.AxisAlignedBoundingBox(
        min_bound=np.array(min_bound),
        max_bound=np.array(max_bound)
    )
    return pcd.crop(bbox)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="View point cloud map")
    parser.add_argument("map_file", help="Path to map file (.ply, .pcd)")
    args = parser.parse_args()

    pcd = load_map(args.map_file)
    o3d.visualization.draw_geometries([pcd])
