#!/usr/bin/env python3
"""
Vehicle Mapping Pipeline - Main Script

This script runs the complete mapping pipeline:
1. Load PCD sequence from 32-line LiDAR
2. Run KISS-ICP odometry
3. Optimize pose graph with GTSAM
4. (Optional) Detect and add loop closures
5. Build point cloud map with Open3D
6. Extract waypoints for path-following

Usage:
    python run_pipeline.py /path/to/pcds -o output_dir
    python run_pipeline.py /path/to/pcds -o output_dir --loop-closure --visualize
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
except ImportError:
    print("Please install pyyaml: pip install pyyaml")
    sys.exit(1)

from src.pcd_loader import PCDLoader
from src.kiss_icp_runner import KissICPRunner
from src.simple_icp import SimpleICPOdometry
from src.pose_graph import PoseGraphOptimizer
from src.loop_detector import LoopDetector
from src.map_builder import MapBuilder
from src.waypoint_extractor import WaypointExtractor, save_trajectory


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def print_header():
    """Print pipeline header."""
    print("=" * 60)
    print("  Vehicle Mapping Pipeline")
    print("  KISS-ICP + GTSAM + Open3D")
    print("=" * 60)
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Vehicle Mapping Pipeline - Build maps from PCD sequences',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic mapping
  python run_pipeline.py ./data/pcds -o ./output

  # With loop closure detection
  python run_pipeline.py ./data/pcds -o ./output --loop-closure

  # With visualization
  python run_pipeline.py ./data/pcds -o ./output --visualize
        """
    )

    parser.add_argument('data_dir', help='Directory containing PCD files')
    parser.add_argument('--output', '-o', default='output',
                        help='Output directory (default: output)')
    parser.add_argument('--config', '-c', default='config/mapping_config.yaml',
                        help='Configuration file')
    parser.add_argument('--loop-closure', '-l', action='store_true',
                        help='Enable loop closure detection')
    parser.add_argument('--visualize', '-v', action='store_true',
                        help='Visualize results')
    parser.add_argument('--save-intermediate', action='store_true',
                        help='Save intermediate results (odometry poses)')
    parser.add_argument('--simple-icp', action='store_true',
                        help='Use Simple ICP instead of KISS-ICP (for compatibility)')

    args = parser.parse_args()

    print_header()

    # Setup paths
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load config
    config_path = Path(__file__).parent.parent / args.config
    config = load_config(str(config_path))

    # =========================================================================
    # Step 1: Load PCD sequence
    # =========================================================================
    print("[1/5] Loading PCD sequence...")

    try:
        loader = PCDLoader(str(data_dir), config.get('loader', {}))
        pcd_files, point_clouds = loader.load_sequence(preprocess=True)
        print(f"      Loaded {len(pcd_files)} frames")
        print(f"      Sample frame: {len(point_clouds[0])} points")
    except Exception as e:
        print(f"      Error: {e}")
        sys.exit(1)

    # =========================================================================
    # Step 2: Run ICP odometry
    # =========================================================================
    print("\n[2/5] Running ICP odometry...")

    odom_poses = None

    # Use Simple ICP if requested or as fallback
    if args.simple_icp:
        print("      Using Simple ICP (Open3D)...")
        try:
            simple_icp = SimpleICPOdometry(config.get('icp', {}))
            odom_poses = simple_icp.run_on_sequence(point_clouds, verbose=True)
            print(f"      Computed {len(odom_poses)} poses")
        except Exception as e:
            print(f"      Error: {e}")
            sys.exit(1)
    else:
        # Try KISS-ICP
        try:
            print("      Using KISS-ICP...")
            kiss_icp = KissICPRunner(config.get('kiss_icp', {}))
            odom_poses = kiss_icp.run_on_sequence(point_clouds)
            print(f"      Computed {len(odom_poses)} poses")
        except Exception as e:
            print(f"      KISS-ICP failed: {e}")
            print("      Try --simple-icp flag for compatibility")
            sys.exit(1)

    if args.save_intermediate:
        odom_path = output_dir / 'odometry_poses.npy'
        np.save(str(odom_path), odom_poses)
        print(f"      Saved odometry to {odom_path}")

    # =========================================================================
    # Step 3: GTSAM pose graph optimization
    # =========================================================================
    print("\n[3/5] Optimizing pose graph with GTSAM...")

    try:
        optimizer = PoseGraphOptimizer(config.get('gtsam', {}))
        optimized_poses = optimizer.build_from_odometry(odom_poses)

        # Optional: Loop closure
        if args.loop_closure:
            print("      Detecting loop closures...")
            loop_detector = LoopDetector(config.get('loop_closure', {}))

            # Build point cloud dict
            cloud_dict = {i: point_clouds[i] for i in range(len(point_clouds))}

            # Detect and verify loops
            loops = loop_detector.detect_and_verify(optimized_poses, cloud_dict)

            if loops:
                print(f"      Adding {len(loops)} loop closure constraints...")
                for id_from, id_to, T_loop in loops:
                    optimizer.add_loop_closure(id_from, id_to, T_loop)

                # Re-optimize with loops
                optimized_poses = optimizer.optimize()

        stats = optimizer.get_statistics()
        print(f"      Optimized {stats['n_poses']} poses")
        print(f"      Factors: {stats['n_odom_factors']} odom + {stats['n_loop_factors']} loops")

    except ImportError as e:
        print(f"      Warning: GTSAM not available, using odometry directly")
        print(f"      Install GTSAM: conda install -c conda-forge gtsam")
        optimized_poses = {i: odom_poses[i] for i in range(len(odom_poses))}

    # =========================================================================
    # Step 4: Build point cloud map
    # =========================================================================
    print("\n[4/5] Building point cloud map with Open3D...")

    def progress_callback(current, total):
        if current % 50 == 0 or current == total:
            print(f"      Progress: {current}/{total} frames", end='\r')

    map_builder = MapBuilder(config.get('map', {}))
    global_map = map_builder.build_map(point_clouds, optimized_poses, progress_callback)
    print()  # New line after progress

    stats = map_builder.get_statistics()
    print(f"      Map points: {stats['n_points']}")
    print(f"      Bounds: {stats['bounds_min']} to {stats['bounds_max']}")

    # =========================================================================
    # Step 5: Save outputs
    # =========================================================================
    print("\n[5/5] Saving outputs...")

    # Save map
    map_builder.save_map(str(output_dir / 'map.ply'))
    map_builder.save_map(str(output_dir / 'map.pcd'))

    # Save trajectory
    save_trajectory(optimized_poses, str(output_dir / 'trajectory.txt'))
    print(f"      Saved trajectory to {output_dir / 'trajectory.txt'}")

    # Extract and save waypoints
    extractor = WaypointExtractor(config.get('waypoints', {}))
    waypoints = extractor.extract(optimized_poses)
    extractor.save_waypoints(waypoints, str(output_dir / 'waypoints.txt'))

    wp_stats = extractor.compute_statistics(waypoints)
    print(f"      Extracted {wp_stats['n_waypoints']} waypoints")
    print(f"      Path length: {wp_stats['total_length']:.2f} m")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("  Pipeline Complete!")
    print("=" * 60)
    print(f"\n  Output directory: {output_dir.absolute()}")
    print(f"  - map.ply          : Point cloud map")
    print(f"  - map.pcd          : Point cloud map (PCD format)")
    print(f"  - trajectory.txt   : Optimized poses")
    print(f"  - waypoints.txt    : Path waypoints")
    print()

    # Copy waypoints hint
    print("  To use with vehicle-path-following:")
    print(f"    cp {output_dir / 'waypoints.txt'} ../vehicle-path-following/data/")
    print()

    # Visualization
    if args.visualize:
        print("  Opening visualization...")
        map_builder.visualize("Vehicle Map")


if __name__ == '__main__':
    main()
