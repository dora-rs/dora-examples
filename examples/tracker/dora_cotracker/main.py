"""Dora CoTracker Node.

This node uses Facebook's CoTracker to track points across video frames.
It can receive points from bounding box detections or manual input.
"""

import argparse
import os
from collections import deque

import cv2
import numpy as np
import pyarrow as pa
import torch
from cotracker.predictor import CoTrackerOnlinePredictor
from dora import Node

DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
WINDOW_SIZE = int(os.getenv("COTRACKER_WINDOW_SIZE", "16"))
INTERACTIVE_MODE = os.getenv("INTERACTIVE_MODE", "false").lower() == "true"
CHECKPOINT = os.getenv("COTRACKER_CHECKPOINT", None)


def bbox_to_points(bbox: np.ndarray, num_points: int = 5) -> np.ndarray:
    """Convert bounding box to tracking points.

    Parameters
    ----------
    bbox : np.ndarray
        Bounding box in format [x1, y1, x2, y2]
    num_points : int
        Number of points to generate inside the box

    Returns
    -------
    np.ndarray
        Array of points [[x1, y1], [x2, y2], ...] in shape (N, 2)
    """
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    w, h = x2 - x1, y2 - y1

    # Generate points: center + corners
    points = [
        [cx, cy],  # center
        [x1 + w * 0.25, y1 + h * 0.25],  # top-left quadrant
        [x1 + w * 0.75, y1 + h * 0.25],  # top-right quadrant
        [x1 + w * 0.25, y1 + h * 0.75],  # bottom-left quadrant
        [x1 + w * 0.75, y1 + h * 0.75],  # bottom-right quadrant
    ]
    return np.array(points[:num_points], dtype=np.float32)


def draw_tracked_points(frame: np.ndarray, points: np.ndarray, visibility: np.ndarray = None) -> np.ndarray:
    """Draw tracked points on frame.

    Parameters
    ----------
    frame : np.ndarray
        Input frame (H, W, C)
    points : np.ndarray
        Tracked points (N, 2)
    visibility : np.ndarray, optional
        Visibility mask (N,)

    Returns
    -------
    np.ndarray
        Frame with drawn points
    """
    output = frame.copy()
    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (255, 0, 255), (0, 255, 255),
        (128, 0, 128), (255, 165, 0), (0, 128, 128),
    ]

    for i, point in enumerate(points):
        if visibility is not None and not visibility[i]:
            continue
        x, y = int(point[0]), int(point[1])
        color = colors[i % len(colors)]
        cv2.circle(output, (x, y), 5, color, -1)
        cv2.circle(output, (x, y), 7, (255, 255, 255), 1)

    return output


def main():
    """Main function for CoTracker node."""
    parser = argparse.ArgumentParser(description="Dora CoTracker Node")
    parser.add_argument("--name", type=str, default="dora-cotracker")
    args = parser.parse_args()

    # Initialize CoTracker
    print(f"Loading CoTracker on device: {DEVICE}")
    if CHECKPOINT:
        model = CoTrackerOnlinePredictor(checkpoint=CHECKPOINT)
    else:
        model = torch.hub.load("facebookresearch/co-tracker", "cotracker3_online")
    model = model.to(DEVICE)

    node = Node(args.name)

    # Frame buffer for video processing
    frame_buffer = deque(maxlen=WINDOW_SIZE)
    current_points = None
    frame_count = 0
    is_first_step = True
    latest_image_id = None
    latest_frame = None

    for event in node:
        if event["type"] == "INPUT":
            event_id = event["id"]
            metadata = event["metadata"]

            if event_id == "image":
                # Receive image frame
                storage = event["value"]
                height = int(metadata.get("height", 480))
                width = int(metadata.get("width", 640))
                encoding = metadata.get("encoding", "rgb8")
                channels = 3 if encoding in ["rgb8", "bgr8"] else 1

                frame = (
                    storage.to_numpy(zero_copy_only=False)
                    .astype(np.uint8)
                    .reshape((height, width, channels))
                )

                # Convert BGR to RGB if needed
                if encoding == "bgr8":
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                latest_frame = frame
                latest_image_id = metadata.get("image_id", str(frame_count))
                frame_count += 1

                # Add to buffer and process
                frame_buffer.append(frame)

                if current_points is not None and len(frame_buffer) >= 2:
                    # Process frames with CoTracker
                    video_chunk = np.stack(list(frame_buffer), axis=0)
                    video_tensor = (
                        torch.from_numpy(video_chunk)
                        .permute(0, 3, 1, 2)
                        .unsqueeze(0)
                        .float()
                        .to(DEVICE)
                    )

                    try:
                        if is_first_step:
                            # Initialize tracking with query points
                            # Query format: (t, x, y) where t is frame index
                            queries = torch.zeros((1, current_points.shape[0], 3), device=DEVICE)
                            queries[0, :, 1:] = torch.from_numpy(current_points).to(DEVICE)

                            pred_tracks, pred_visibility = model(
                                video_chunk=video_tensor,
                                is_first_step=True,
                                queries=queries,
                            )
                            is_first_step = False
                        else:
                            pred_tracks, pred_visibility = model(
                                video_chunk=video_tensor,
                                is_first_step=False,
                            )

                        # Get latest tracked points
                        if pred_tracks is not None:
                            # pred_tracks shape: (B, T, N, 2)
                            tracked_points = pred_tracks[0, -1].cpu().numpy()  # (N, 2)
                            visibility = pred_visibility[0, -1].cpu().numpy() if pred_visibility is not None else None

                            # Draw tracked points on frame
                            tracked_frame = draw_tracked_points(latest_frame, tracked_points, visibility)

                            # Send tracked image
                            node.send_output(
                                "tracked_image",
                                pa.array(tracked_frame.ravel()),
                                metadata={
                                    "width": str(width),
                                    "height": str(height),
                                    "encoding": "rgb8",
                                    "image_id": latest_image_id,
                                },
                            )

                            # Send tracked points
                            node.send_output(
                                "points",
                                pa.array(tracked_points.ravel().astype(np.float32)),
                                metadata={
                                    "num_points": str(len(tracked_points)),
                                    "image_id": latest_image_id,
                                },
                            )
                    except Exception as e:
                        print(f"CoTracker error: {e}")

            elif event_id in ["boxes2d", "points_to_track"]:
                # Receive bounding boxes or points to track
                storage = event["value"]
                encoding = metadata.get("encoding", "xyxy")

                try:
                    # Handle YOLO struct output: {"bbox": [...], "conf": [...], "labels": [...]}
                    if hasattr(storage, "to_pylist"):
                        data_list = storage.to_pylist()
                        if data_list and isinstance(data_list[0], dict) and "bbox" in data_list[0]:
                            # Extract bbox from YOLO output format
                            bbox_coords = []
                            for item in data_list:
                                bbox_coords.extend(item.get("bbox", []))
                            data = np.array(bbox_coords, dtype=np.float32)
                        else:
                            data = np.array(data_list, dtype=np.float32)
                    else:
                        data = storage.to_numpy(zero_copy_only=False).astype(np.float32)
                except Exception as e:
                    print(f"Error parsing bbox data: {e}")
                    continue

                if event_id == "boxes2d":
                    # Convert bboxes to tracking points
                    if len(data) >= 4:
                        # Reshape to (N, 4) where each row is [x1, y1, x2, y2]
                        bboxes = data.reshape(-1, 4)

                        # Generate tracking points from bboxes
                        all_points = []
                        for bbox in bboxes:
                            points = bbox_to_points(bbox)
                            all_points.append(points)

                        if all_points:
                            current_points = np.vstack(all_points)
                            is_first_step = True  # Reset tracking with new points
                            frame_buffer.clear()
                            print(f"New tracking points: {current_points.shape}")
                else:
                    # Direct points input (N, 2)
                    current_points = data.reshape(-1, 2)
                    is_first_step = True
                    frame_buffer.clear()
                    print(f"Direct tracking points: {current_points.shape}")


if __name__ == "__main__":
    main()
