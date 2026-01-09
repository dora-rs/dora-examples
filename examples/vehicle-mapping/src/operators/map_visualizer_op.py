#!/usr/bin/env python3
"""
Map Visualizer Operator for DORA

Visualizes mapping progress using Rerun.

Inputs:
    - pointcloud: Current point cloud
    - pose: Current pose
    - frame_info: Frame metadata
    - map_stats: Map statistics
    - waypoints: Extracted waypoints
"""

import numpy as np
import pyarrow as pa
from dora import DoraStatus

try:
    import rerun as rr
    RERUN_AVAILABLE = True
except ImportError:
    RERUN_AVAILABLE = False
    print("[MapVisualizer] Warning: rerun not available. Install with: pip install rerun-sdk")


class Operator:
    """DORA Operator for Map Visualization."""

    def __init__(self):
        self.initialized = False
        self.trajectory = []
        self.frame_count = 0

        if RERUN_AVAILABLE:
            rr.init("vehicle_mapping", spawn=True)
            self.initialized = True
            print("[MapVisualizer] Rerun initialized")

            # Setup 3D view
            rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
        else:
            print("[MapVisualizer] Running without visualization")

    def on_event(self, dora_event, send_output) -> str:
        if not self.initialized:
            return DoraStatus.CONTINUE

        if dora_event["type"] == "INPUT":
            event_id = dora_event["id"]

            if event_id == "pointcloud":
                # Visualize current point cloud
                points_flat = dora_event["value"].to_numpy()
                if len(points_flat) > 0:
                    points = points_flat.reshape(-1, 3)
                    # Subsample for visualization
                    step = max(1, len(points) // 5000)
                    points_vis = points[::step]

                    rr.log(
                        "world/current_scan",
                        rr.Points3D(points_vis, colors=[100, 150, 255], radii=0.02)
                    )

            elif event_id == "pose":
                # Visualize current pose and trajectory
                pose_flat = dora_event["value"].to_numpy()
                if len(pose_flat) == 16:
                    pose = pose_flat.reshape(4, 4)
                    pos = pose[:3, 3]

                    # Add to trajectory
                    self.trajectory.append(pos.copy())
                    self.frame_count += 1

                    # Visualize robot position
                    rr.log(
                        "world/robot",
                        rr.Points3D([pos], colors=[255, 0, 0], radii=0.15)
                    )

                    # Visualize trajectory
                    if len(self.trajectory) >= 2:
                        traj_array = np.array(self.trajectory)
                        rr.log(
                            "world/trajectory",
                            rr.LineStrips3D([traj_array], colors=[0, 255, 0], radii=0.03)
                        )

                    # Visualize coordinate frame
                    R = pose[:3, :3]
                    arrow_len = 0.3
                    x_axis = pos + R @ np.array([arrow_len, 0, 0])
                    y_axis = pos + R @ np.array([0, arrow_len, 0])
                    z_axis = pos + R @ np.array([0, 0, arrow_len])

                    rr.log(
                        "world/robot/x_axis",
                        rr.Arrows3D(origins=[pos], vectors=[x_axis - pos], colors=[255, 0, 0])
                    )
                    rr.log(
                        "world/robot/y_axis",
                        rr.Arrows3D(origins=[pos], vectors=[y_axis - pos], colors=[0, 255, 0])
                    )

            elif event_id == "frame_info":
                # Log frame info as text
                info = dora_event["value"].to_numpy()
                if len(info) >= 3:
                    frame_idx = int(info[0])
                    total_frames = int(info[1])
                    n_points = int(info[2])

                    rr.log(
                        "status/frame",
                        rr.TextLog(f"Frame {frame_idx}/{total_frames} ({n_points} points)")
                    )

            elif event_id == "map_stats":
                # Log map statistics
                stats = dora_event["value"].to_numpy()
                if len(stats) >= 3:
                    n_points = int(stats[0])
                    n_frames = int(stats[1])
                    size_mb = stats[2]

                    rr.log(
                        "status/map",
                        rr.TextLog(f"Map: {n_points} points, {n_frames} frames, {size_mb:.1f}MB")
                    )

            elif event_id == "waypoints":
                # Visualize extracted waypoints
                wp_flat = dora_event["value"].to_numpy()
                if len(wp_flat) >= 2:
                    waypoints = wp_flat.reshape(-1, 2)
                    # Add Z coordinate
                    wp_3d = np.column_stack([waypoints, np.zeros(len(waypoints))])

                    rr.log(
                        "world/waypoints",
                        rr.Points3D(wp_3d, colors=[255, 255, 0], radii=0.1)
                    )

                    # Connect waypoints with lines
                    if len(wp_3d) >= 2:
                        rr.log(
                            "world/waypoint_path",
                            rr.LineStrips3D([wp_3d], colors=[255, 200, 0], radii=0.02)
                        )

                    print(f"[MapVisualizer] Displayed {len(waypoints)} waypoints")

        elif dora_event["type"] == "STOP":
            print(f"[MapVisualizer] Stopped. Visualized {self.frame_count} frames")
            return DoraStatus.STOP

        return DoraStatus.CONTINUE
