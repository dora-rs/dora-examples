# Python Dora-Zenoh Integration Example

This example shows how to connect Dora with [Zenoh](https://zenoh.io/) for bidirectional communication using Python.

## Overview

Two components communicate with each other:

1. **Dora Node** (Python): Publishes to and subscribes from Zenoh topics
2. **Zenoh App** (Python): Exchanges messages with the Dora node through Zenoh

## Structure

- `dataflow.yml`: Dora dataflow configuration
- `dora_node.py`: The Dora node implementation with Zenoh integration
- `zenoh_app.py`: A standalone Zenoh application
- `requirements.txt`: Python dependencies

## Prerequisites

- Python 3.8+
- Dora installed and available in your PATH or set via the `DORA` environment variable
- Python packages: `dora-rs` and `eclipse-zenoh`

## Installation

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## How It Works

- **Dora Node**:
  - Publishes "Hello" messages to `dora/data` every 500ms
  - Subscribes to messages on `zenoh/data`
  - Runs continuously until Ctrl+C

- **Zenoh App**:
  - Subscribes to `dora/data`
  - After receiving 5 messages, starts publishing to `zenoh/data`
  - Continues both receiving and publishing until Ctrl+C

## Running the Example

### Option 1: Manual Run (Recommended for Testing)

**Terminal 1 - Start Dora dataflow:**
```bash
dora up
dora start dataflow.yml
```

**Terminal 2 - Run Zenoh app:**
```bash
python3 zenoh_app.py
```

To stop:
- Press `Ctrl+C` in Terminal 2 to stop the Zenoh app
- Press `Ctrl+C` in Terminal 1 to stop the Dora node, or run:
```bash
dora destroy dataflow.yml
```

### Option 2: Using Dora Daemon

```bash
dora daemon --run-dataflow dataflow.yml
```

Then in another terminal:
```bash
python3 zenoh_app.py
```

## Expected Output

**From dora_node.py:**
```
Initializing Zenoh session...
Declaring Zenoh publisher for 'dora/data'...
Declaring Zenoh subscriber for 'zenoh/data'...
Dora node with Zenoh integration started!
Press Ctrl+C to stop...
Publishing message: Hello from Dora node! Message #1
Publishing message: Hello from Dora node! Message #2
Publishing message: Hello from Dora node! Message #3
...
>> [Subscriber] Received PUT ('zenoh/data': 'Hello from Zenoh app, payload counter: 0')
>> [Subscriber] Received PUT ('zenoh/data': 'Hello from Zenoh app, payload counter: 1')
...
(continues until Ctrl+C)
```

**From zenoh_app.py:**
```
Opening Zenoh session...
Subscribing to dora/data...
Waiting for 5 messages from Dora node before publishing...
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #1')
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #2')
...
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #5')

Received 5 messages! Creating publisher for 'zenoh/data'...
Publishing to Dora node (Press Ctrl+C to stop)...

<< [Publisher] Sent payload(counter = 0)
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #6')
<< [Publisher] Sent payload(counter = 1)
>> [Subscriber] Received PUT ('dora/data': 'Hello from Dora node! Message #7')
...
(continues bidirectional communication until Ctrl+C)
```

## Troubleshooting

- Ensure Zenoh can communicate (check firewall settings)
- Make sure both `dora-rs` and `eclipse-zenoh` are installed
- Check that Python 3.8+ is being used
