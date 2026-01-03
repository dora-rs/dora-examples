#!/usr/bin/env python3
"""
Simple test script to verify UR5 connection via RTDE.
Run this to test connectivity before using the DORA driver.
"""

import socket
import struct
import time


def test_rtde_connection(host: str = "127.0.0.1", port: int = 30004):
    """Test RTDE connection and read joint positions."""
    print(f"Testing RTDE connection to {host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        print("  [OK] TCP connection established")

        # Request protocol version 2
        size = 5  # 2 + 1 + 2
        header = struct.pack(">HBH", size, 86, 2)  # 86 = 'V' = REQUEST_PROTOCOL_VERSION
        sock.sendall(header)

        resp_header = sock.recv(3)
        resp_size, resp_type = struct.unpack(">HB", resp_header)
        resp_payload = sock.recv(resp_size - 3)

        if resp_type == 86 and resp_payload[0] == 1:
            print("  [OK] RTDE protocol version 2 accepted")
        else:
            print("  [WARN] Protocol version response:", resp_payload)

        # Setup output recipe for actual_q (joint positions)
        recipe = "actual_q"
        payload = recipe.encode("utf-8")
        size = len(payload) + 3
        header = struct.pack(">HB", size, 79)  # 79 = 'O' = SETUP_OUTPUTS
        sock.sendall(header + payload)

        resp_header = sock.recv(3)
        resp_size, resp_type = struct.unpack(">HB", resp_header)
        resp_payload = sock.recv(resp_size - 3)

        if resp_type == 79 and len(resp_payload) > 0:
            recipe_id = resp_payload[0]
            print(f"  [OK] Output recipe setup (ID: {recipe_id})")
        else:
            print("  [FAIL] Failed to setup output recipe")
            return False

        # Start synchronization
        header = struct.pack(">HB", 3, 83)  # 83 = 'S' = START
        sock.sendall(header)

        resp_header = sock.recv(3)
        resp_size, resp_type = struct.unpack(">HB", resp_header)
        resp_payload = sock.recv(resp_size - 3) if resp_size > 3 else b""

        if resp_type == 83 and len(resp_payload) > 0 and resp_payload[0] == 1:
            print("  [OK] RTDE synchronization started")
        else:
            print("  [FAIL] Failed to start synchronization")
            return False

        # Receive data package
        print("  Reading joint positions...")
        for i in range(3):
            resp_header = sock.recv(3)
            resp_size, resp_type = struct.unpack(">HB", resp_header)
            resp_payload = sock.recv(resp_size - 3)

            if resp_type == 85:  # 85 = 'U' = DATA_PACKAGE
                # Parse 6 doubles (actual_q)
                joints = struct.unpack_from(">6d", resp_payload, 1)
                print(f"  Joint positions: [{', '.join(f'{j:.4f}' for j in joints)}]")
                break
            time.sleep(0.1)

        sock.close()
        print("\n[SUCCESS] RTDE connection test passed!")
        return True

    except socket.timeout:
        print("  [FAIL] Connection timeout")
        return False
    except ConnectionRefusedError:
        print("  [FAIL] Connection refused - is URSim running and robot powered on?")
        return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def test_urscript_connection(host: str = "127.0.0.1", port: int = 30002):
    """Test URScript connection."""
    print(f"\nTesting URScript connection to {host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        print("  [OK] URScript interface connected")
        sock.close()
        return True
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def test_dashboard_connection(host: str = "127.0.0.1", port: int = 29999):
    """Test Dashboard Server connection."""
    print(f"\nTesting Dashboard Server connection to {host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))

        # Read welcome message
        welcome = sock.recv(1024).decode("utf-8")
        print(f"  Dashboard: {welcome.strip()}")

        # Get robot mode
        sock.sendall(b"robotmode\n")
        response = sock.recv(1024).decode("utf-8")
        print(f"  Robot mode: {response.strip()}")

        sock.close()
        return True
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


if __name__ == "__main__":
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"

    print("=" * 50)
    print("UR5 Connection Test")
    print("=" * 50)

    dashboard_ok = test_dashboard_connection(host)
    rtde_ok = test_rtde_connection(host)
    urscript_ok = test_urscript_connection(host)

    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Dashboard Server: {'OK' if dashboard_ok else 'FAIL'}")
    print(f"  RTDE Interface:   {'OK' if rtde_ok else 'FAIL'}")
    print(f"  URScript:         {'OK' if urscript_ok else 'FAIL'}")
    print("=" * 50)

    if rtde_ok and urscript_ok:
        print("\nReady to run DORA dataflow!")
        sys.exit(0)
    else:
        print("\nPlease check URSim is running and robot is powered on.")
        sys.exit(1)
