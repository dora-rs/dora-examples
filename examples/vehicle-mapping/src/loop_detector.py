#!/usr/bin/env python3
"""
Loop Detector - Detect and verify loop closures.

Loop closure detection finds when the robot revisits a previously
visited location, allowing the pose graph to be corrected.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False


class LoopDetector:
    """Detect loop closures using distance and ICP verification."""

    def __init__(self, config: dict = None):
        """
        Initialize loop detector.

        Args:
            config: Configuration dictionary with optional keys:
                - distance_threshold: Max distance to consider loop (default: 5.0)
                - min_frame_gap: Minimum frames between loop candidates (default: 50)
                - icp_fitness_threshold: ICP fitness for verification (default: 0.3)
                - icp_max_correspondence: ICP correspondence distance (default: 0.5)
        """
        config = config or {}

        self.distance_threshold = config.get('distance_threshold', 5.0)
        self.min_frame_gap = config.get('min_frame_gap', 50)
        self.icp_fitness_threshold = config.get('icp_fitness_threshold', 0.3)
        self.icp_max_correspondence = config.get('icp_max_correspondence', 0.5)

    def detect_candidates(self, poses: Dict[int, np.ndarray]) -> List[Tuple[int, int]]:
        """
        Find loop closure candidates based on spatial distance.

        Args:
            poses: Dictionary of pose ID to 4x4 transformation matrix

        Returns:
            List of (id_from, id_to) tuples representing loop candidates
        """
        candidates = []
        pose_ids = sorted(poses.keys())

        # Extract positions
        positions = {k: poses[k][:3, 3] for k in pose_ids}

        for i, id_i in enumerate(pose_ids):
            for j, id_j in enumerate(pose_ids):
                # Skip if not enough frame gap
                if id_j - id_i < self.min_frame_gap:
                    continue

                # Check distance
                dist = np.linalg.norm(positions[id_i] - positions[id_j])
                if dist < self.distance_threshold:
                    candidates.append((id_i, id_j))

        return candidates

    def verify_loop(self, cloud_i: np.ndarray, cloud_j: np.ndarray,
                    initial_guess: np.ndarray = None) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Verify loop closure with ICP.

        Args:
            cloud_i: Nx3 point cloud from frame i
            cloud_j: Mx3 point cloud from frame j
            initial_guess: Initial 4x4 transformation guess

        Returns:
            Tuple of (success, transformation, fitness)
        """
        if not OPEN3D_AVAILABLE:
            raise ImportError("open3d not installed")

        if initial_guess is None:
            initial_guess = np.eye(4)

        # Create Open3D point clouds
        pcd_i = o3d.geometry.PointCloud()
        pcd_i.points = o3d.utility.Vector3dVector(cloud_i.astype(np.float64))

        pcd_j = o3d.geometry.PointCloud()
        pcd_j.points = o3d.utility.Vector3dVector(cloud_j.astype(np.float64))

        # Downsample for faster ICP
        voxel_size = 0.2
        pcd_i_down = pcd_i.voxel_down_sample(voxel_size)
        pcd_j_down = pcd_j.voxel_down_sample(voxel_size)

        # Run ICP
        result = o3d.pipelines.registration.registration_icp(
            pcd_i_down, pcd_j_down,
            self.icp_max_correspondence,
            initial_guess,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50)
        )

        success = result.fitness > self.icp_fitness_threshold
        return success, result.transformation, result.fitness

    def detect_and_verify(self, poses: Dict[int, np.ndarray],
                          point_clouds: Dict[int, np.ndarray]) -> List[Tuple[int, int, np.ndarray]]:
        """
        Detect and verify all loop closures.

        Args:
            poses: Dictionary of pose ID to 4x4 matrix
            point_clouds: Dictionary of pose ID to Nx3 point cloud

        Returns:
            List of (id_from, id_to, relative_transform) for verified loops
        """
        candidates = self.detect_candidates(poses)
        verified_loops = []

        print(f"[LoopDetector] Found {len(candidates)} loop candidates")

        for id_i, id_j in candidates:
            if id_i not in point_clouds or id_j not in point_clouds:
                continue

            # Initial guess from current poses
            initial_guess = np.linalg.inv(poses[id_i]) @ poses[id_j]

            success, transform, fitness = self.verify_loop(
                point_clouds[id_i],
                point_clouds[id_j],
                initial_guess
            )

            if success:
                verified_loops.append((id_i, id_j, transform))
                print(f"[LoopDetector] Verified loop: {id_i} -> {id_j} (fitness: {fitness:.3f})")

        print(f"[LoopDetector] Verified {len(verified_loops)} loop closures")
        return verified_loops


class ScanContextDetector:
    """
    Loop closure detection using Scan Context descriptors.

    Scan Context is a global descriptor for place recognition in LiDAR scans.
    This is more robust than distance-based detection for complex environments.

    Reference: https://github.com/irapkaist/scancontext
    """

    def __init__(self, config: dict = None):
        """
        Initialize Scan Context detector.

        Args:
            config: Configuration with:
                - num_sectors: Number of sectors (default: 60)
                - num_rings: Number of rings (default: 20)
                - max_range: Maximum range (default: 80.0)
                - similarity_threshold: Matching threshold (default: 0.1)
        """
        config = config or {}

        self.num_sectors = config.get('num_sectors', 60)
        self.num_rings = config.get('num_rings', 20)
        self.max_range = config.get('max_range', 80.0)
        self.similarity_threshold = config.get('similarity_threshold', 0.1)

        self.descriptors = {}

    def compute_descriptor(self, points: np.ndarray) -> np.ndarray:
        """
        Compute Scan Context descriptor for a point cloud.

        Args:
            points: Nx3 point cloud

        Returns:
            num_rings x num_sectors descriptor matrix
        """
        # Convert to polar coordinates
        x, y, z = points[:, 0], points[:, 1], points[:, 2]
        ranges = np.sqrt(x**2 + y**2)
        angles = np.arctan2(y, x)  # -pi to pi

        # Normalize to grid indices
        range_idx = np.clip(
            (ranges / self.max_range * self.num_rings).astype(int),
            0, self.num_rings - 1
        )
        angle_idx = np.clip(
            ((angles + np.pi) / (2 * np.pi) * self.num_sectors).astype(int),
            0, self.num_sectors - 1
        )

        # Build descriptor (max height in each bin)
        descriptor = np.zeros((self.num_rings, self.num_sectors))
        for i in range(len(points)):
            r, a = range_idx[i], angle_idx[i]
            descriptor[r, a] = max(descriptor[r, a], z[i])

        return descriptor

    def add_frame(self, frame_id: int, points: np.ndarray):
        """Add frame to database."""
        self.descriptors[frame_id] = self.compute_descriptor(points)

    def find_matches(self, query_id: int, min_gap: int = 50) -> List[Tuple[int, float]]:
        """
        Find matching frames for a query.

        Args:
            query_id: Query frame ID
            min_gap: Minimum frame gap

        Returns:
            List of (frame_id, similarity) tuples
        """
        if query_id not in self.descriptors:
            return []

        query_desc = self.descriptors[query_id]
        matches = []

        for frame_id, desc in self.descriptors.items():
            if abs(frame_id - query_id) < min_gap:
                continue

            # Compute similarity (using correlation)
            similarity = self._compute_similarity(query_desc, desc)
            if similarity > self.similarity_threshold:
                matches.append((frame_id, similarity))

        return sorted(matches, key=lambda x: -x[1])

    def _compute_similarity(self, desc1: np.ndarray, desc2: np.ndarray) -> float:
        """Compute similarity between two descriptors."""
        # Try different column shifts to handle rotation
        best_sim = 0
        for shift in range(self.num_sectors):
            shifted = np.roll(desc2, shift, axis=1)
            # Cosine similarity
            norm1 = np.linalg.norm(desc1)
            norm2 = np.linalg.norm(shifted)
            if norm1 > 0 and norm2 > 0:
                sim = np.sum(desc1 * shifted) / (norm1 * norm2)
                best_sim = max(best_sim, sim)
        return best_sim
