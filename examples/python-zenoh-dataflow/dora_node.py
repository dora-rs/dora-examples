#!/usr/bin/env python3
"""
Dora node that integrates with Zenoh.
- Receives tick events from Dora
- Publishes messages to Zenoh topic 'dora/data'
- Subscribes to Zenoh topic 'zenoh/data'
- Runs continuously until Ctrl+C
"""

import zenoh
from dora import Node

def main():
    # Initialize the Dora node
    node = Node()

    # Initialize Zenoh
    print("Initializing Zenoh session...")
    config = zenoh.Config()
    session = zenoh.open(config)

    print("Declaring Zenoh publisher for 'dora/data'...")
    publisher = session.declare_publisher("dora/data")

    print("Declaring Zenoh subscriber for 'zenoh/data'...")
    subscriber = session.declare_subscriber("zenoh/data")

    print("Dora node with Zenoh integration started!")
    print("Press Ctrl+C to stop...")

    message_counter = 0

    # Process events
    try:
        for event in node:
            event_type = event["type"]

            if event_type == "INPUT":
                # Handle Dora input events
                input_id = event["id"]

                if input_id == "tick":
                    # Increment counter for message numbering
                    message_counter += 1

                    # Create a hello message
                    message = f"Hello from Dora node! Message #{message_counter}"

                    # Publish to Zenoh
                    print(f"Publishing message: {message}")
                    publisher.put(message)

            elif event_type == "STOP":
                print("Received stop signal")
                break

            elif event_type == "INPUT_CLOSED":
                print(f"Input `{event['id']}` was closed")

            # Check for Zenoh messages (non-blocking)
            try:
                sample = subscriber.try_recv()
                if sample is not None:
                    payload = sample.payload.to_string()
                    print(f">> [Subscriber] Received {sample.kind} ('{sample.key_expr}': '{payload}')")
            except:
                pass  # No message available

    except KeyboardInterrupt:
        print("\nReceived Ctrl+C, shutting down...")

    # Cleanup
    session.close()
    print("Dora node exited successfully")

if __name__ == "__main__":
    main()
