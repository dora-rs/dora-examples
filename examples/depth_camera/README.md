# Depth Camera Example

This example demonstrates capturing RGB images and depth data from depth cameras, with visualization in [Rerun](https://rerun.io/).

## Overview

The dataflow captures frames from a depth camera (Intel RealSense or iOS LiDAR), outputs both RGB image and depth data, and displays them in the Rerun viewer.

```
depth_camera -> rerun (display RGB + depth)
```

### Supported Devices

- **Intel RealSense**: D400 series depth cameras (D415, D435, D455, etc.)
- **iOS LiDAR**: iPhone Pro / iPad Pro with LiDAR scanner

### Nodes

- **camera**: Captures RGB image and depth data from the depth camera
  - `dora-pyrealsense` for Intel RealSense
  - `dora-ios-lidar` for iOS devices
- **plot**: Visualizes the RGB image and depth data in Rerun viewer using `dora-rerun`

## Prerequisites

- Python 3.8+
- One of the following depth cameras:
  - Intel RealSense D400 series camera
  - iPhone Pro / iPad Pro with LiDAR

### For Intel RealSense

- [librealsense2](https://github.com/IntelRealSense/librealsense) SDK installed

### For iOS LiDAR

- iOS device with LiDAR (iPhone 12 Pro or later, iPad Pro 2020 or later)
- [Record3D](https://record3d.app/) app installed on iOS device

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

### 2. Run the dataflow

#### For Intel RealSense

```bash
cd examples/depth_camera

# Start dora daemon
dora up

# Build and start the dataflow
dora build realsense.yaml
dora start realsense.yaml
```

#### For iOS LiDAR

1. Open Record3D app on your iOS device
2. Enable USB streaming mode in Record3D settings
3. Connect iOS device via USB

```bash
cd examples/depth_camera

# Start dora daemon
dora up

# Build and start the dataflow
dora build ios.yaml
dora start ios.yaml
```

### 3. View the output

Connect Rerun viewer to see the RGB and depth streams:

```bash
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

### 4. Stop the dataflow

```bash
dora stop
```

## Configuration

### iOS LiDAR Node

Configure via environment variables in `ios.yaml` or `ios-dev.yaml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `IMAGE_WIDTH` | Output image width | `640` |
| `IMAGE_HEIGHT` | Output image height | `480` |

## Dataflow Variants

This example includes multiple dataflow configurations:

- **realsense.yaml**: Intel RealSense camera (production)
- **realsense-dev.yaml**: Intel RealSense camera (development, editable install)
- **ios.yaml**: iOS LiDAR camera (production)
- **ios-dev.yaml**: iOS LiDAR camera (development, editable install)

## Troubleshooting

### Intel RealSense Not Detected

- Ensure librealsense2 SDK is installed
- Check USB connection (use USB 3.0 port for best performance)
- Try running with sudo if permission denied: use `realsense-dev.yaml` which includes sudo

### iOS Device Not Detected

- Ensure Record3D app is running and USB streaming is enabled
- Check USB connection between iOS device and computer
- Trust the computer on your iOS device when prompted

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

## Architecture

```
+---------------+     +------+
| depth_camera  | --> | plot |
| (image+depth) |     +------+
+---------------+
```

## Source Code

- [dora-pyrealsense](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-pyrealsense) - Intel RealSense camera node
- [dora-ios-lidar](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-ios-lidar) - iOS LiDAR camera node
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun) - Rerun visualization node
