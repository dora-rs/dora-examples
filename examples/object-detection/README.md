# Object Detection Example

This example demonstrates real-time object detection using [YOLO](https://docs.ultralytics.com/) (You Only Look Once) with dora-rs, and visualization in [Rerun](https://rerun.io/).

## Overview

The dataflow captures frames from your webcam, processes them through YOLO for object detection, and visualizes the results with bounding boxes in Rerun.

```
camera -> dora-yolo (object detection) -> rerun (display with bounding boxes)
```

### Nodes

- **camera**: Captures frames from your webcam using `opencv-video-capture`
- **object-detection**: Detects objects in frames using `dora-yolo` (YOLOv8)
- **plot**: Visualizes the camera feed with bounding boxes using `dora-rerun`

## Prerequisites

- A webcam connected to your computer
- Python 3.8+
- dora-rs

## Getting Started

### 1. Install dora

```bash
# Install dora CLI
cargo install dora-cli

# Install Python package (must match CLI version)
pip install dora-rs
```

**Important**: Ensure the `dora` CLI version matches the `dora-rs` Python package version:

```bash
dora --version      # Check CLI version
pip show dora-rs    # Check Python package version
```

### 2. Build and Run

```bash
cd examples/object-detection

# Build the dataflow
dora build yolo.yml

# Start dora daemon
dora up

# Start the dataflow
dora start yolo.yml
```

#### Using UV (recommended)

```bash
uv venv --seed -p 3.11
dora build yolo.yml --uv
dora run yolo.yml --uv
```

### 3. View the output

Connect Rerun viewer to see the video stream with detected objects:

```bash
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

### 4. Stop the dataflow

```bash
dora stop
```

## Configuration

### Camera Node

Configure via environment variables in `yolo.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `CAPTURE_PATH` | Camera device index | `0` |
| `IMAGE_WIDTH` | Output image width | `640` |
| `IMAGE_HEIGHT` | Output image height | `480` |

### YOLO Node

The `dora-yolo` node uses YOLOv8 by default. It can detect 80 common object classes from the COCO dataset including:
- People, vehicles (car, bus, truck, bicycle, motorcycle)
- Animals (dog, cat, bird, horse, etc.)
- Common objects (chair, table, laptop, phone, etc.)

## Outputs

The `dora-yolo` node outputs:

- **bbox**: Bounding box coordinates and class labels for detected objects in each frame

## Architecture

```
+--------+     +------------------+     +------+
| camera | --> | object-detection | --> | plot |
+--------+     | (dora-yolo)      |     +------+
    |          +------------------+         ^
    |                                       |
    +---------------------------------------+
                  (image)
```

## Troubleshooting

### Model Download

On first run, YOLO will automatically download the model weights. This may take a moment depending on your internet connection.

### Camera Not Working

- Check camera permissions on macOS: System Preferences > Privacy & Security > Camera
- Try different `CAPTURE_PATH` values (0, 1, 2...)

### Version Mismatch Error

If you see errors like `invalid type: map, expected a YAML tag starting with '!'`:

```bash
# Check versions match
dora --version
pip show dora-rs

# Upgrade if needed
cargo install dora-cli --version X.Y.Z
pip install dora-rs==X.Y.Z
```

## Source Code

- [dora-yolo](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-yolo) - YOLO object detection node
- [opencv-video-capture](https://github.com/dora-rs/dora-hub/tree/main/node-hub/opencv-video-capture) - Camera capture node
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun) - Rerun visualization node
