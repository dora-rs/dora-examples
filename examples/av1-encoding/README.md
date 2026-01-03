# AV1 Encoding Example

This example demonstrates real-time AV1 video encoding and decoding using [rav1e](https://github.com/xiph/rav1e) (encoder) and [dav1d](https://code.videolan.org/videolan/dav1d) (decoder), with visualization in [Rerun](https://rerun.io/).

## Overview

The dataflow captures webcam frames, encodes them with AV1, decodes them, re-encodes, decodes again, and displays the result. This simulates a round-trip encoding pipeline useful for testing video compression quality.

```
camera -> rav1e (encode) -> dav1d (decode) -> rav1e (encode) -> dav1d (decode) -> rerun (display)
```

### Nodes

- **camera**: Captures frames from your webcam using `opencv-video-capture`
- **rav1e-local**: Encodes frames to AV1 format using `dora-rav1e`
- **dav1d-remote**: Decodes AV1 frames using `dora-dav1d`
- **rav1e-remote**: Re-encodes decoded frames to AV1
- **dav1d-local**: Final decode of AV1 frames
- **plot**: Visualizes the decoded frames in Rerun viewer using `dora-rerun`

## Prerequisites

- Rust toolchain (for building rav1e/dav1d nodes)
- Python 3.8+
- Webcam

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

### 2. Clone dora-hub (for node sources)

```bash
git clone https://github.com/dora-rs/dora-hub.git
cd dora-hub
```

### 3. Build the nodes

```bash
# Build AV1 encoder/decoder nodes
cargo build -p dora-rav1e --release
cargo build -p dora-dav1d --release

# Install Python nodes
pip install -e node-hub/opencv-video-capture
pip install -e node-hub/dora-rerun
```

### 4. Run the dataflow

```bash
cd examples/av1-encoding

# Start dora daemon
dora up

# Build and start the dataflow
dora build dataflow.yml
dora start dataflow.yml
```

### 5. View the output

Connect Rerun viewer to see the video stream:

```bash
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

### 6. Stop the dataflow

```bash
dora stop
```

## Configuration

### Camera Node

Configure via environment variables in `dataflow.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `CAPTURE_PATH` | Camera device index | `0` |
| `IMAGE_WIDTH` | Output image width | `1280` |
| `IMAGE_HEIGHT` | Output image height | `720` |

### AV1 Encoder (rav1e)

| Variable | Description | Default |
|----------|-------------|---------|
| `RAV1E_SPEED` | Encoding speed preset (0-10, higher = faster) | `10` |

## Dataflow Variants

This example includes multiple dataflow configurations:

- **dataflow.yml**: Local machine version (single machine, recommended)
- **dataflow_distributed.yml**: Distributed deployment version (requires dora daemons on `encoder` and `decoder` machines)


## Troubleshooting

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

### Node Not Found Error

If nodes fail to spawn with "No such file or directory":

1. Ensure you built the Rust nodes: `cargo build -p dora-rav1e -p dora-dav1d --release`
2. Check the `path` in dataflow.yml points to the correct binary location

### Camera Not Working

- Check camera permissions on macOS: System Preferences > Privacy & Security > Camera
- Try different `CAPTURE_PATH` values (0, 1, 2...)

## Architecture


```
+--------+     +-------------+     +-------------+
| camera | --> | rav1e-local | --> | dav1d-remote|
+--------+     +-------------+     +-------------+
                                          |
                                          v
+------+     +------------+     +--------------+
| plot | <-- | dav1d-local| <-- | rav1e-remote |
+------+     +------------+     +--------------+
```

## Source Code

- [dora-rav1e](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rav1e) - AV1 encoder node
- [dora-dav1d](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-dav1d) - AV1 decoder node
- [opencv-video-capture](https://github.com/dora-rs/dora-hub/tree/main/node-hub/opencv-video-capture) - Camera capture node
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun) - Rerun visualization node
