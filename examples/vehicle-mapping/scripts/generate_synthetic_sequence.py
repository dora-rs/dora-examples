#!/usr/bin/env python3
"""
Generate Synthetic PCD Sequence from Waypoints

This script creates a synthetic LiDAR point cloud sequence by:
1. Reading waypoints from a trajectory file
2. Interpolating poses along the path
3. Simulating LiDAR scans at each pose (with walls/features for ICP)
4. Saving as PCD sequence

The generated sequence can be used to test the mapping pipeline,
and the output waypoints should match the input route.

Usage:
    python generate_synthetic_sequence.py ../vehicle-path-following/data/sample_waypoints.txt -o data/rectangle_sequence
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple
import numpy as np

try:
    import open3d as o3d
except ImportError:
    print("Please install open3d: pip install open3d")
    sys.exit(1)


def load_waypoints(filepath: str) -> np.ndarray:
    """Load waypoints from file (x y format, with comments)."""
    waypoints = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                x, y = float(parts[0]), float(parts[1])
                waypoints.append([x, y])
    return np.array(waypoints)


def interpolate_path(waypoints: np.ndarray, spacing: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Interpolate waypoints to create evenly spaced poses.

    Args:
        waypoints: Nx2 array of (x, y) waypoints
        spacing: Distance between interpolated points

    Returns:
        positions: Mx2 array of interpolated positions
        headings: M array of heading angles (radians)
    """
    positions = [waypoints[0]]

    for i in range(1, len(waypoints)):
        start = waypoints[i-1]
        end = waypoints[i]

        dist = np.linalg.norm(end - start)
        if dist < 1e-6:
            continue

        n_steps = max(1, int(dist / spacing))

        for j in range(1, n_steps + 1):
            t = j / n_steps
            pos = start + t * (end - start)
            positions.append(pos)

    positions = np.array(positions)

    # Compute headings (direction of travel)
    headings = []
    for i in range(len(positions)):
        if i < len(positions) - 1:
            dx = positions[i+1, 0] - positions[i, 0]
            dy = positions[i+1, 1] - positions[i, 1]
        else:
            dx = positions[i, 0] - positions[i-1, 0]
            dy = positions[i, 1] - positions[i-1, 1]
        headings.append(np.arctan2(dy, dx))

    return positions, np.array(headings)


def create_environment_walls(route_center: np.ndarray, corridor_width: float = 2.0,
                            wall_height: float = 2.0, point_density: float = 0.05) -> np.ndarray:
    """
    Create wall points around the rectangular route with distinctive features.

    Args:
        route_center: Nx2 array of route center points
        corridor_width: Width of corridor (distance between walls)
        wall_height: Height of walls
        point_density: Spacing between wall points

    Returns:
        Mx3 array of wall points
    """
    wall_points = []
    half_width = corridor_width / 2

    # Get bounds of route
    x_min, y_min = route_center.min(axis=0) - corridor_width
    x_max, y_max = route_center.max(axis=0) + corridor_width

    # Create INNER corridor walls (closer to the route for better ICP)
    inner_offset = 0.8  # Distance from route center to inner walls

    # Create walls along the route segments
    for i in range(len(route_center) - 1):
        p1, p2 = route_center[i], route_center[i + 1]
        direction = p2 - p1
        length = np.linalg.norm(direction)
        if length < 0.01:
            continue
        direction = direction / length
        normal = np.array([-direction[1], direction[0]])  # Perpendicular

        # Create wall points along this segment (both sides)
        for t in np.arange(0, length, point_density):
            point = p1 + t * direction
            for z in np.arange(0, wall_height, point_density):
                # Left wall
                wall_points.append([point[0] + normal[0] * inner_offset,
                                   point[1] + normal[1] * inner_offset, z])
                # Right wall
                wall_points.append([point[0] - normal[0] * inner_offset,
                                   point[1] - normal[1] * inner_offset, z])

    # Create outer boundary walls (for global reference)
    for x in np.arange(x_min, x_max, point_density * 2):
        for z in np.arange(0, wall_height, point_density * 2):
            wall_points.append([x, y_min - half_width, z])
            wall_points.append([x, y_max + half_width, z])

    for y in np.arange(y_min, y_max, point_density * 2):
        for z in np.arange(0, wall_height, point_density * 2):
            wall_points.append([x_min - half_width, y, z])
            wall_points.append([x_max + half_width, y, z])

    # Dense ground plane with distinctive grid pattern
    for x in np.arange(x_min, x_max, point_density):
        for y in np.arange(y_min, y_max, point_density):
            wall_points.append([x, y, 0.0])

    # Add pillars at ALL waypoints (not just corners) for distinctive features
    for i, wp in enumerate(route_center):
        pillar_radius = 0.15
        for angle in np.arange(0, 2*np.pi, 0.15):
            for z in np.arange(0, wall_height, point_density):
                # Offset pillar to the side so it doesn't block the path
                offset = 0.5 if i % 2 == 0 else -0.5
                wall_points.append([
                    wp[0] + offset + pillar_radius * np.cos(angle),
                    wp[1] + pillar_radius * np.sin(angle),
                    z
                ])

    # Add large corner structures for very distinctive features at corners
    corner_positions = [
        (route_center[0], 'start'),
        (route_center[len(route_center)//4], 'corner1'),
        (route_center[len(route_center)//2], 'corner2'),
        (route_center[3*len(route_center)//4], 'corner3'),
        (route_center[-1], 'end'),
    ]

    for corner, name in corner_positions:
        # Large L-shaped structure at corners
        for dx in np.arange(-0.5, 0.5, point_density):
            for z in np.arange(0, wall_height * 1.5, point_density):
                wall_points.append([corner[0] + dx + 1.0, corner[1], z])
                wall_points.append([corner[0], corner[1] + dx + 1.0, z])

    return np.array(wall_points)


def simulate_lidar_scan(sensor_pos: np.ndarray, sensor_heading: float,
                        environment: np.ndarray, max_range: float = 20.0,
                        n_beams_horizontal: int = 360, n_beams_vertical: int = 32,
                        fov_vertical: float = 40.0) -> np.ndarray:
    """
    Simulate a 32-line LiDAR scan from given position.

    Args:
        sensor_pos: (x, y) position of sensor
        sensor_heading: Heading angle in radians
        environment: Mx3 array of environment points
        max_range: Maximum LiDAR range
        n_beams_horizontal: Number of horizontal beams (angular resolution)
        n_beams_vertical: Number of vertical beams (e.g., 32 for 32-line LiDAR)
        fov_vertical: Vertical field of view in degrees

    Returns:
        Nx3 array of points in sensor frame
    """
    # Sensor is at height 1.5m (typical vehicle LiDAR mount)
    sensor_z = 1.5
    sensor_3d = np.array([sensor_pos[0], sensor_pos[1], sensor_z])

    # Get points within range
    distances = np.linalg.norm(environment - sensor_3d, axis=1)
    in_range = distances < max_range
    visible_points = environment[in_range]

    if len(visible_points) == 0:
        return np.zeros((0, 3))

    # Transform to sensor frame
    # Rotation matrix for sensor heading (around Z axis)
    cos_h, sin_h = np.cos(-sensor_heading), np.sin(-sensor_heading)
    R = np.array([
        [cos_h, -sin_h, 0],
        [sin_h, cos_h, 0],
        [0, 0, 1]
    ])

    # Translate and rotate
    local_points = (visible_points - sensor_3d) @ R.T

    # Add some noise to simulate real LiDAR
    noise = np.random.normal(0, 0.02, local_points.shape)  # 2cm noise
    local_points += noise

    return local_points


def create_se3_pose(x: float, y: float, z: float, heading: float) -> np.ndarray:
    """Create SE3 transformation matrix from position and heading."""
    cos_h, sin_h = np.cos(heading), np.sin(heading)
    T = np.eye(4)
    T[:3, :3] = np.array([
        [cos_h, -sin_h, 0],
        [sin_h, cos_h, 0],
        [0, 0, 1]
    ])
    T[:3, 3] = [x, y, z]
    return T


def save_pcd(points: np.ndarray, filepath: str):
    """Save points as PCD file."""
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    o3d.io.write_point_cloud(filepath, pcd)


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic PCD sequence from waypoints')
    parser.add_argument('waypoints_file', help='Path to waypoints file')
    parser.add_argument('--output', '-o', default='data/synthetic_rectangle',
                        help='Output directory for PCD sequence')
    parser.add_argument('--spacing', type=float, default=0.5,
                        help='Spacing between frames (meters)')
    parser.add_argument('--max-frames', type=int, default=None,
                        help='Maximum number of frames to generate')
    parser.add_argument('--visualize', '-v', action='store_true',
                        help='Visualize the environment and trajectory')

    args = parser.parse_args()

    print("=" * 60)
    print("  Synthetic PCD Sequence Generator")
    print("=" * 60)
    print()

    # Load waypoints
    print(f"[1/4] Loading waypoints from {args.waypoints_file}...")
    waypoints = load_waypoints(args.waypoints_file)
    print(f"      Loaded {len(waypoints)} waypoints")
    print(f"      Route bounds: ({waypoints[:,0].min():.1f}, {waypoints[:,1].min():.1f}) to ({waypoints[:,0].max():.1f}, {waypoints[:,1].max():.1f})")

    # Interpolate path
    print(f"\n[2/4] Interpolating path (spacing={args.spacing}m)...")
    positions, headings = interpolate_path(waypoints, args.spacing)

    if args.max_frames and len(positions) > args.max_frames:
        step = len(positions) // args.max_frames
        positions = positions[::step]
        headings = headings[::step]

    print(f"      Generated {len(positions)} poses")

    # Create environment
    print("\n[3/4] Creating environment (walls, ground, pillars)...")
    environment = create_environment_walls(positions)
    print(f"      Environment has {len(environment)} points")

    # Generate PCD sequence
    print(f"\n[4/4] Generating LiDAR scans...")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    ground_truth_poses = []

    for i, (pos, heading) in enumerate(zip(positions, headings)):
        # Simulate LiDAR scan
        scan = simulate_lidar_scan(pos, heading, environment)

        # Save PCD
        pcd_path = output_dir / f"frame_{i:04d}.pcd"
        save_pcd(scan, str(pcd_path))

        # Store ground truth pose
        T = create_se3_pose(pos[0], pos[1], 1.5, heading)
        ground_truth_poses.append(T)

        if (i + 1) % 10 == 0 or i == len(positions) - 1:
            print(f"      Progress: {i+1}/{len(positions)} frames")

    # Save ground truth
    gt_path = output_dir / "ground_truth_poses.npy"
    np.save(str(gt_path), np.array(ground_truth_poses))

    # Save waypoints copy for reference
    wp_path = output_dir / "original_waypoints.txt"
    with open(wp_path, 'w') as f:
        f.write("# Original waypoints used to generate this sequence\n")
        for x, y in waypoints:
            f.write(f"{x:.3f} {y:.3f}\n")

    print()
    print("=" * 60)
    print("  Generation Complete!")
    print("=" * 60)
    print(f"\n  Output directory: {output_dir.absolute()}")
    print(f"  - {len(positions)} PCD files (frame_0000.pcd ... frame_{len(positions)-1:04d}.pcd)")
    print(f"  - ground_truth_poses.npy: Ground truth SE3 poses")
    print(f"  - original_waypoints.txt: Copy of input waypoints")
    print()
    print("  To run the mapping pipeline:")
    print(f"    python scripts/run_pipeline.py {output_dir} -o output/rectangle_test --simple-icp")
    print()

    # Optional visualization
    if args.visualize:
        print("  Opening visualization...")

        # Create point clouds
        env_pcd = o3d.geometry.PointCloud()
        env_pcd.points = o3d.utility.Vector3dVector(environment)
        env_pcd.paint_uniform_color([0.7, 0.7, 0.7])  # Gray walls

        # Trajectory as line set
        traj_points = np.column_stack([positions, np.ones(len(positions)) * 1.5])
        lines = [[i, i+1] for i in range(len(positions)-1)]
        line_set = o3d.geometry.LineSet()
        line_set.points = o3d.utility.Vector3dVector(traj_points)
        line_set.lines = o3d.utility.Vector2iVector(lines)
        line_set.colors = o3d.utility.Vector3dVector([[1, 0, 0] for _ in lines])  # Red trajectory

        # Waypoint markers
        wp_pcd = o3d.geometry.PointCloud()
        wp_3d = np.column_stack([waypoints, np.ones(len(waypoints)) * 1.5])
        wp_pcd.points = o3d.utility.Vector3dVector(wp_3d)
        wp_pcd.paint_uniform_color([0, 1, 0])  # Green waypoints

        o3d.visualization.draw_geometries(
            [env_pcd, line_set, wp_pcd],
            window_name="Synthetic Environment",
            width=1200, height=800
        )


if __name__ == '__main__':
    main()
