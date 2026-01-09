#!/usr/bin/env python3
"""
Visualize point cloud map and trajectory.

Usage:
    python visualize_map.py output/map.ply
    python visualize_map.py output/map.ply --trajectory output/trajectory.txt
"""

import argparse
import sys
from pathlib import Path

import numpy as np

try:
    import open3d as o3d
except ImportError:
    print("Please install open3d: pip install open3d")
    sys.exit(1)


def load_trajectory(trajectory_file: str) -> np.ndarray:
    """Load trajectory from file."""
    positions = []

    with open(trajectory_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) >= 4:
                # Format: id x y z ...
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                positions.append([x, y, z])

    return np.array(positions)


def create_trajectory_lineset(positions: np.ndarray, color: list = [1, 0, 0]) -> o3d.geometry.LineSet:
    """Create line set from trajectory positions."""
    n_points = len(positions)

    lines = [[i, i + 1] for i in range(n_points - 1)]
    colors = [color for _ in range(len(lines))]

    line_set = o3d.geometry.LineSet()
    line_set.points = o3d.utility.Vector3dVector(positions)
    line_set.lines = o3d.utility.Vector2iVector(lines)
    line_set.colors = o3d.utility.Vector3dVector(colors)

    return line_set


def create_coordinate_frame(size: float = 1.0) -> o3d.geometry.TriangleMesh:
    """Create coordinate frame at origin."""
    return o3d.geometry.TriangleMesh.create_coordinate_frame(size=size)


def color_by_height(pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """Color point cloud by height (Z coordinate)."""
    points = np.asarray(pcd.points)
    z = points[:, 2]

    z_min, z_max = z.min(), z.max()
    z_norm = (z - z_min) / (z_max - z_min + 1e-6)

    # Color map: blue (low) -> green -> yellow -> red (high)
    colors = np.zeros((len(points), 3))

    for i, zn in enumerate(z_norm):
        if zn < 0.25:
            # Blue to Cyan
            t = zn / 0.25
            colors[i] = [0, t, 1]
        elif zn < 0.5:
            # Cyan to Green
            t = (zn - 0.25) / 0.25
            colors[i] = [0, 1, 1 - t]
        elif zn < 0.75:
            # Green to Yellow
            t = (zn - 0.5) / 0.25
            colors[i] = [t, 1, 0]
        else:
            # Yellow to Red
            t = (zn - 0.75) / 0.25
            colors[i] = [1, 1 - t, 0]

    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd


def main():
    parser = argparse.ArgumentParser(description='Visualize point cloud map')
    parser.add_argument('map_file', help='Path to map file (.ply, .pcd)')
    parser.add_argument('--trajectory', '-t', help='Path to trajectory file')
    parser.add_argument('--waypoints', '-w', help='Path to waypoints file')
    parser.add_argument('--voxel-size', '-v', type=float, default=0,
                        help='Voxel size for downsampling (0 = no downsampling)')
    parser.add_argument('--no-color', action='store_true',
                        help='Do not apply height coloring')

    args = parser.parse_args()

    # Load map
    print(f"Loading map from {args.map_file}...")
    pcd = o3d.io.read_point_cloud(args.map_file)
    print(f"  Loaded {len(pcd.points)} points")

    # Optional downsampling
    if args.voxel_size > 0:
        pcd = pcd.voxel_down_sample(args.voxel_size)
        print(f"  After downsampling: {len(pcd.points)} points")

    # Color by height
    if not args.no_color and not pcd.has_colors():
        pcd = color_by_height(pcd)

    geometries = [pcd, create_coordinate_frame()]

    # Load trajectory
    if args.trajectory:
        print(f"Loading trajectory from {args.trajectory}...")
        positions = load_trajectory(args.trajectory)
        print(f"  Loaded {len(positions)} poses")

        trajectory_lines = create_trajectory_lineset(positions, color=[1, 0, 0])
        geometries.append(trajectory_lines)

    # Load waypoints
    if args.waypoints:
        print(f"Loading waypoints from {args.waypoints}...")
        waypoints = []
        with open(args.waypoints, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    waypoints.append([float(parts[0]), float(parts[1]), 0.5])

        if waypoints:
            wp_pcd = o3d.geometry.PointCloud()
            wp_pcd.points = o3d.utility.Vector3dVector(np.array(waypoints))
            wp_pcd.paint_uniform_color([0, 1, 0])  # Green
            geometries.append(wp_pcd)
            print(f"  Loaded {len(waypoints)} waypoints")

    # Visualize
    print("\nOpening visualization...")
    print("  Controls:")
    print("    Mouse drag: Rotate")
    print("    Scroll: Zoom")
    print("    Shift + drag: Pan")
    print("    R: Reset view")
    print("    Q: Quit")

    o3d.visualization.draw_geometries(
        geometries,
        window_name="Vehicle Map Viewer",
        width=1280,
        height=720,
        point_show_normal=False
    )


if __name__ == '__main__':
    main()
