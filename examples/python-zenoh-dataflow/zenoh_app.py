#!/usr/bin/env python3
"""
Standalone Zenoh application that communicates with the Dora node.
- Subscribes to 'dora/data' (receives from Dora node)
- After receiving 5 messages, starts publishing to 'zenoh/data'
- Runs continuously until Ctrl+C
"""

import time
import zenoh

def main():
    # Hardcoded parameters
    subscribe_topic = "dora/data"
    publish_topic = "zenoh/data"

    print(f"Zenoh App - Will subscribe to: {subscribe_topic}")

    # Initialize Zenoh
    print("Opening Zenoh session...")
    config = zenoh.Config()
    session = zenoh.open(config)

    # Subscribe to the topic
    print(f"Subscribing to {subscribe_topic}...")
    subscriber = session.declare_subscriber(subscribe_topic)

    # Receive 5 messages first before starting to publish
    count = 0
    print("Waiting for 5 messages from Dora node before publishing...")
    try:
        while count < 5:
            sample = subscriber.recv()
            if sample is not None:
                payload = sample.payload.to_string()
                print(f">> [Subscriber] Received {sample.kind} ('{sample.key_expr}': '{payload}')")
                count += 1
    except KeyboardInterrupt:
        print("\nExiting before publishing phase...")
        session.close()
        return

    # Create a publisher for sending messages back to Dora
    print(f"\nReceived 5 messages! Creating publisher for '{publish_topic}'...")
    publisher = session.declare_publisher(publish_topic)

    # Start publishing messages and continue receiving
    counter = 0
    print("Publishing to Dora node (Press Ctrl+C to stop)...\n")

    try:
        while True:
            # Continue receiving messages from Dora
            try:
                sample = subscriber.try_recv()
                if sample is not None:
                    payload = sample.payload.to_string()
                    print(f">> [Subscriber] Received {sample.kind} ('{sample.key_expr}': '{payload}')")
            except:
                pass  # No message available

            # Publish message
            time.sleep(1)
            message = f"Hello from Zenoh app, payload counter: {counter}"
            print(f"<< [Publisher] Sent payload(counter = {counter})")
            publisher.put(message)
            counter += 1
    except KeyboardInterrupt:
        print("\n\nReceived Ctrl+C, exiting...")

    session.close()
    print("Zenoh app exited successfully")

if __name__ == "__main__":
    main()
