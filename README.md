# Examples for Dora-rs

This repo provides standalone examples for Dora-rs.

## Quick Start Examples

| Example | Description |
|---------|-------------|
| [camera](./examples/camera/README.md) | Webcam capture and display using opencv-video-capture |
| [python-dataflow](./examples/python-dataflow/README.md) | Python nodes dataflow example |
| [llm](./examples/llm/README.md) | LLM integration example |
| [object-detection](./examples/object-detection/README.md) | Object detection example |
| [lebai](./examples/lebai/README.md) | Lebai robot arm driver example |

## Rust/C++ Examples

```bash
DORA=<DORA REPO PATH> [ROS=<ROS SOURCE FILE>] cargo run --example <example-name> [--release]
```

Available examples:
- cxx-dataflow
- cxx-ros2-dataflow
- cxx-arrow-dataflow
- c-dataflow
- rust-dataflow
- rust-ros2-dataflow
- rust-dataflow-url
- rust-dataflow-git
- multiple-daemons
- [customed-ros2-dataflow](./examples/customed-ros2-dataflow/README.md)
- python-zenoh-dataflow
- rust-zenoh-dataflow
- python-distributed-zenoh
