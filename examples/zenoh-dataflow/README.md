# Dora-Zenoh Integration Example

This example shows how to connect Dora with [Zenoh](https://zenoh.io/) for bidirectional communication.

## Overview

Two components communicate with each other:

1. **Dora Node**: Publishes to and subscribes from Zenoh topics
2. **Zenoh App**: Exchanges messages with the Dora node through Zenoh

## Structure

- `dataflow.yml`: Dora dataflow configuration
- `dora-node/`: The Dora node implementation with Zenoh integration
- `zenoh-app/`: A standalone Zenoh application that subscribes to data
- `main.rs`: Runner for the Dora dataflow

## Prerequisites

- Rust and Cargo
- Dora installed and available in your PATH or set via the `DORA` environment variable
- Zenoh dependencies installed

- make sure DORA env is setup correctly
```
export DORA=/Users/demo/dora
```
## How It Works

```
  nodes:
      - id: dora-zenoh-publisher
        build: bash -c "cd dora-node && cargo build --release"  # Build command
        path: ./dora-node/target/aarch64-apple-darwin/release/dora-node  # Binary path
        inputs:
            tick: dora/timer/millis/500  # Input: timer ticks every 500ms

  - id: Node identifier
  - build: Command to compile the node
  - path: Where to find the compiled binary
  - inputs: Dora provides a timer that sends ticks every 500ms to this node
```
- **Dora Node**:
  - Publishes "Hello" messages to `dora/data`
  - Subscribes to messages on `zenoh/data`

- **Zenoh App**:
  - Subscribes to `zenoh/data`
  - Publishes messages to `dora/data`

```
 cargo run --release --example zenoh-dataflow
```

```
2025-11-02T18:10:49.943542Z  INFO dora_daemon::log:    Initializing Zenoh session... build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
2025-11-02T18:10:49.951918Z  INFO dora_daemon::log:    Declaring Zenoh publisher for 'dora/data'... build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #1')
2025-11-02T18:10:49.962553Z  INFO dora_daemon::log:    Declaring Zenoh subscriber for 'zenoh/data'... build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
2025-11-02T18:10:49.972699Z  INFO dora_daemon::log:    Dora node with Zenoh integration started! build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
2025-11-02T18:10:49.977408Z  INFO dora_daemon::log:    Publishing message: Hello from Dora node! Message #1 build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
2025-11-02T18:10:50.444696Z  INFO dora_daemon::log:    Publishing message: Hello from Dora node! Message #2 build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #2')
2025-11-02T18:10:50.944559Z  INFO dora_daemon::log:    Publishing message: Hello from Dora node! Message #3 build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #3')
2025-11-02T18:10:51.445510Z  INFO dora_daemon::log:    Publishing message: Hello from Dora node! Message #4 build_id=None dataflow_id=Some("019a45c3-c5d2-7725-85d1-e741573b765e") node_id=Some("dora-zenoh-publisher")
```
