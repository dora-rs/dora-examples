#!/bin/bash
# Simple test script to debug Dora distributed setup

echo "=== Testing Dora Distributed Setup ==="
echo ""

# Clean up
echo "1. Cleaning up any existing processes..."
pkill -f "dora coordinator" 2>/dev/null
pkill -f "dora daemon" 2>/dev/null
sleep 2

# Test coordinator
echo ""
echo "2. Starting coordinator..."
dora coordinator &
COORDINATOR_PID=$!
echo "   Coordinator PID: $COORDINATOR_PID"
sleep 5

if ! ps -p $COORDINATOR_PID > /dev/null; then
    echo "   ERROR: Coordinator is not running!"
    exit 1
fi
echo "   ✓ Coordinator is running"

# Test one daemon
echo ""
echo "3. Starting edge1 daemon..."
dora daemon --machine-id edge1 &
DAEMON1_PID=$!
echo "   Daemon PID: $DAEMON1_PID"
sleep 3

if ! ps -p $DAEMON1_PID > /dev/null; then
    echo "   ERROR: Daemon edge1 failed to start or crashed!"
    kill $COORDINATOR_PID 2>/dev/null
    exit 1
fi
echo "   ✓ Daemon edge1 is running"

# List running dora processes
echo ""
echo "4. Current Dora processes:"
ps aux | grep -E "dora (coordinator|daemon)" | grep -v grep

echo ""
echo "5. Testing dora list command..."
dora list

echo ""
echo "=== All tests passed! ==="
echo "Press Ctrl+C to stop all processes"
echo ""

trap "echo ''; echo 'Cleaning up...'; kill $COORDINATOR_PID $DAEMON1_PID 2>/dev/null; exit 0" INT

wait
