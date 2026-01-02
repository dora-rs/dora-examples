# Rerun Viewer Example

This example shows how to capture webcam frames and visualize them using [Rerun](https://rerun.io/).

## Overview

The [`dataflow.yml`](./dataflow.yml) defines a simple dataflow graph with two nodes:

- **camera**: Captures frames from your webcam using `opencv-video-capture`
- **rerun**: Visualizes the captured frames in Rerun viewer using `dora-rerun`

## Getting Started

Make sure to have `dora` installed.

```bash
pip install dora-rs
```

### Build and Run

```bash
cd examples/rerun-viewer
dora build dataflow.yml
dora up
dora start dataflow.yml
```

## Configuration

You can configure the camera node via environment variables in `dataflow.yml`:

- `CAPTURE_PATH`: Camera device index (default: `0`)
- `IMAGE_WIDTH`: Output image width (default: `640`)
- `IMAGE_HEIGHT`: Output image height (default: `480`)
- `ENCODING`: Image encoding format (default: `rgb8`)
