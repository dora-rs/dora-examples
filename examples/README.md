# Dora Examples

This directory contains example projects demonstrating various dora-rs capabilities.

## Getting Started

Each example includes its own README with specific instructions. The general pattern is:

```bash
cd examples/<example-name>
dora build dataflow.yml
dora up
dora start dataflow.yml
```

## Available Examples

### Computer Vision

| Example | Description |
|---------|-------------|
| [camera](./camera) | Basic webcam capture and display |
| [depth_camera](./depth_camera) | Depth camera integration |
| [mediapipe](./mediapipe) | Human pose detection using MediaPipe |
| [object-detection](./object-detection) | Object detection pipeline |
| [rerun-viewer](./rerun-viewer) | Visualization with Rerun |
| [tracker](./tracker) | Object tracking |
| [vggt](./vggt) | Visual grounding and tracking |

### AI/ML

| Example | Description |
|---------|-------------|
| [llm](./llm) | Large Language Model integration |
| [vlm](./vlm) | Vision-Language Model integration |
| [translation](./translation) | Translation pipeline |

### Speech

| Example | Description |
|---------|-------------|
| [speech-to-speech](./speech-to-speech) | End-to-end speech pipeline |
| [speech-to-text](./speech-to-text) | Speech recognition |

### Language Integrations

| Example | Description |
|---------|-------------|
| [python-dataflow](./python-dataflow) | Python-based dataflow |
| [python-async](./python-async) | Async Python nodes |
| [python-multi-env](./python-multi-env) | Multiple Python environments |
| [pyarrow-test](./pyarrow-test) | PyArrow data handling |
| [rust-dataflow](./rust-dataflow) | Rust-based dataflow |
| [rust-dataflow-git](./rust-dataflow-git) | Rust nodes from Git |
| [rust-dataflow-url](./rust-dataflow-url) | Rust nodes from URL |
| [c-dataflow](./c-dataflow) | C language integration |
| [cxx-dataflow](./cxx-dataflow) | C++ dataflow |
| [cxx-arrow-dataflow](./cxx-arrow-dataflow) | C++ with Arrow |
| [cmake-dataflow](./cmake-dataflow) | CMake-based build |

### ROS2 Integration

| Example | Description |
|---------|-------------|
| [python-ros2-dataflow](./python-ros2-dataflow) | Python ROS2 integration |
| [rust-ros2-dataflow](./rust-ros2-dataflow) | Rust ROS2 integration |
| [cxx-ros2-dataflow](./cxx-ros2-dataflow) | C++ ROS2 integration |
| [customed-ros2-dataflow](./customed-ros2-dataflow) | Custom ROS2 messages |

### Zenoh

| Example | Description |
|---------|-------------|
| [python-zenoh-dataflow](./python-zenoh-dataflow) | Python Zenoh integration |
| [rust-zenoh-dataflow](./rust-zenoh-dataflow) | Rust Zenoh integration |
| [python-distributed-zenoh](./python-distributed-zenoh) | Distributed Zenoh |

### Robotics

| Example | Description |
|---------|-------------|
| [lebai](./lebai) | Lebai robot integration |
| [mujoco-sim](./mujoco-sim) | MuJoCo simulation |

### Other

| Example | Description |
|---------|-------------|
| [av1-encoding](./av1-encoding) | AV1 video encoding |
| [cuda-benchmark](./cuda-benchmark) | CUDA performance testing |
| [echo](./echo) | Simple echo node |
| [keyboard](./keyboard) | Keyboard input handling |
| [multiple-daemons](./multiple-daemons) | Multiple daemon setup |
| [openai-server](./openai-server) | OpenAI API server |

## Requirements

- dora-rs (`pip install dora-rs`)
- Python 3.8+ (for Python examples)
- Rust toolchain (for Rust examples)
- Additional dependencies as specified in each example's README
