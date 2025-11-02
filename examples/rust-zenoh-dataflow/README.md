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

## How It Works

- **Dora Node**:
  - Publishes "Hello" messages to `dora/data`
  - Subscribes to messages on `zenoh/data`

- **Zenoh App**:
  - Subscribes to `zenoh/data`
  - Publishes messages to `dora/data`
