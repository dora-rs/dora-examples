# MediaPipe Example

This example demonstrates human pose detection using MediaPipe and dora-rs.

## Overview

The [`dataflow.yml`](./dataflow.yml) defines a dataflow graph with three nodes:

- **camera**: Captures frames from your webcam using `opencv-video-capture`
- **dora-mediapipe**: Processes frames to detect human pose landmarks
- **plot**: Visualizes the camera feed and detected pose points using `dora-rerun`

## Requirements

- A webcam connected to your computer
- Python 3.8+
- dora-rs

## Getting Started

Make sure to have `dora` installed:

```bash
pip install dora-rs
```

### Build and Run

```bash
cd examples/mediapipe
dora build dataflow.yml
dora up
dora start dataflow.yml
```

If the points are not plotted by default, try adding a 2D viewer within the Rerun interface.

## Configuration

You can configure the camera node via environment variables in `dataflow.yml`:

- `CAPTURE_PATH`: Camera device index (default: `0`)
- `IMAGE_WIDTH`: Output image width (default: `640`)
- `IMAGE_HEIGHT`: Output image height (default: `480`)
- `ENCODING`: Image encoding format (default: `rgb8`)

## Outputs

The `dora-mediapipe` node outputs:

- `points2d`: 2D pose landmark coordinates detected in each frame

