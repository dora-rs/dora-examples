# ROS2 Integration with Dora

This example demonstrates how to integrate ROS2 nodes with Dora's dataflow framework.

## Prerequisites

- ROS2 installed (tested with ROS2 Jazzy)
- Dora framework installed
- Rust toolchain
- `colcon` build system

## Environment Setup

Set the following environment variables:

```bash
# Point to your Dora repository
export DORA=/path/to/dora

# Point to your ROS2 setup script
export ROS=/opt/ros/jazzy/setup.bash
```

## Examples

### 1. ROS2 Service Integration (Dora as Server)

```bash
cargo run --example customed-ros2-dataflow service
```

Uses `dataflow.yml` and the `add_client` ROS package.

### 2. ROS2 Action Integration (Dora as Client)

```bash
cargo run --example customed-ros2-dataflow action
```

Uses `dataflow_action.yml` and the `fibonacci_action_server` ROS package.

## Usage

```
cargo run --example customed-ros2-dataflow [service|action]
```

- `service`: Dora acts as a server, terminates after ROS client finishes
- `action`: Dora acts as a client, terminates the ROS server after completing its work

## Files

- `main.rs` - Example runner
- `dataflow.yml` - Service example configuration
- `dataflow_action.yml` - Action example configuration
- `dora_nodes/src/dora_server.rs` - ROS2 service server implementation
- `dora_nodes/src/dora_action_client.rs` - ROS2 action client implementation