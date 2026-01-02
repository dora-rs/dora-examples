# Object Tracking Example

## Overview

This dataflow creates a real-time object tracking pipeline using Facebook's CoTracker:

```
Camera -> Object Detection -> CoTracker -> Rerun (Display)
```

The pipeline captures video from your camera, detects objects using YOLO, tracks detected objects across frames using CoTracker, and displays the results in the Rerun viewer.

## Nodes

- **opencv-video-capture**: Captures video from camera
- **dora-yolo**: Object detection using YOLOv8
- **dora-cotracker**: Point tracking using Facebook's CoTracker3
- **dora-rerun**: Visualizes tracking results in Rerun viewer

## Prerequisites

- Python 3.10+
- dora-rs
- Camera (webcam)
- GPU recommended (CUDA, MPS, or CPU fallback)

## Getting Started

### 1. Install dora

```bash
# Install dora CLI
cargo install dora-cli

# Or install Python package (must match CLI version)
pip install dora-rs
```

### 2. Build and Run

```bash
cd examples/tracker

# Build dataflow
dora build facebook_cotracker.yml

# Run dataflow
dora run facebook_cotracker.yml
```

### 3. View Results

```bash
# Connect to Rerun viewer
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

## Configuration

### CoTracker Node Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DEVICE` | Device for inference (cuda/mps/cpu) | Auto-detect |
| `COTRACKER_WINDOW_SIZE` | Frame buffer size for tracking | `16` |
| `INTERACTIVE_MODE` | Enable interactive mode | `false` |
| `COTRACKER_CHECKPOINT` | Custom model checkpoint path | `None` |

### Camera Node Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CAPTURE_PATH` | Camera device index or video path | `0` |
| `IMAGE_WIDTH` | Capture width | `640` |
| `IMAGE_HEIGHT` | Capture height | `480` |
| `ENCODING` | Image encoding (rgb8/bgr8) | `rgb8` |

## Dataflow Variants

- `facebook_cotracker.yml`: Uses YOLO for object detection + CoTracker for tracking
- `qwenvl_cotracker.yml`: Uses Qwen2.5-VL (Vision Language Model) for detection + CoTracker for tracking

## Architecture

### YOLO + CoTracker Pipeline

```
+--------+     +------+     +-----------+     +--------+
| Camera | --> | YOLO | --> | CoTracker | --> | Rerun  |
+--------+     +------+     +-----------+     +--------+
     |                            ^
     |____________________________|
              (image stream)
```

### VLM + CoTracker Pipeline

```
+--------+     +---------+     +------------+     +-----------+     +--------+
| Camera | --> | Qwen-VL | --> | parse_bbox | --> | CoTracker | --> | Rerun  |
+--------+     +---------+     +------------+     +-----------+     +--------+
     |                                                   ^
     |___________________________________________________|
                        (image stream)
```

## How It Works

1. **Object Detection**: YOLO (or VLM) detects objects in each frame and outputs bounding boxes
2. **Point Generation**: CoTracker converts bounding boxes to tracking points (5 points per box)
3. **Point Tracking**: CoTracker tracks these points across consecutive frames using deep learning
4. **Visualization**: Tracked points are drawn on frames and displayed in Rerun

## Troubleshooting

### Camera Issues
- Check system camera permissions
- Verify correct camera device index in `CAPTURE_PATH`
- Test camera in other applications first

### Model Download Slow
- First run downloads CoTracker and YOLO models which may take time
- Ensure stable internet connection
- Models are cached after first download

### GPU Memory Issues
- Reduce `IMAGE_WIDTH` and `IMAGE_HEIGHT` for lower memory usage
- Set `DEVICE=cpu` to use CPU (slower but less memory)
- Reduce `COTRACKER_WINDOW_SIZE` for less frame buffering

### Rerun Version Mismatch
- If you see version warnings, install matching Rerun SDK:
  ```bash
  pip install rerun-sdk==<version>
  ```

## Source Code

- [opencv-video-capture](https://github.com/dora-rs/dora-hub/tree/main/node-hub/opencv-video-capture)
- [dora-yolo](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-yolo)
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun)
- [CoTracker (Facebook Research)](https://github.com/facebookresearch/co-tracker)
