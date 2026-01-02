# Camera Example

This example shows how to capture webcam frames and display them using dora-rs.

## Overview

The [`dataflow.yml`](./dataflow.yml) defines a simple dataflow graph with two nodes:

- **camera**: Captures frames from your webcam using `opencv-video-capture`
- **plot**: Displays the captured frames in a window using `opencv-plot`

## Getting Started

Make sure to have `dora` installed.

```bash
pip install dora-rs
```

### Build and Run

```bash
cd examples/camera
dora build dataflow.yml
dora up
dora start dataflow.yml
```

## Jupyter Notebook Variant

A Jupyter notebook variant is available in [`dataflow_jupyter.yml`](./dataflow_jupyter.yml) with [`notebook.ipynb`](./notebook.ipynb).

```bash
dora build dataflow_jupyter.yml
dora up
dora start dataflow_jupyter.yml
# Then open notebook.ipynb in Jupyter
```

## Configuration

You can configure the camera node via environment variables in `dataflow.yml`:

- `CAPTURE_PATH`: Camera device index (default: `0`)
- `IMAGE_WIDTH`: Output image width (default: `640`)
- `IMAGE_HEIGHT`: Output image height (default: `480`)
