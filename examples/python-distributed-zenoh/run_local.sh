#!/bin/bash
# Script to run distributed sensor network simulation on ONE machine
# This simulates multiple machines using different machine IDs

set -u

PYTHON_BIN=${PYTHON_BIN:-$(command -v python3 || true)}
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: Unable to locate python3. Set PYTHON_BIN to a Python interpreter with dora-rs installed."
  exit 1
fi

PYTHON_DIR=$(dirname "$PYTHON_BIN")
export PATH="$PYTHON_DIR:$PATH"
echo "Using Python interpreter: $PYTHON_BIN"

LOG_DIR=$(mktemp -d 2>/dev/null || mktemp -d -t dora_run)
PIDS=()
DATAFLOW_FILE="dataflow.yml"
COORDINATOR_LOG="$LOG_DIR/coordinator.log"

cleanup() {
  if [ ${#PIDS[@]} -gt 0 ]; then
    for pid in "${PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
  fi
  if [ -n "${DATAFLOW_STARTED:-}" ]; then
    dora destroy "$DATAFLOW_FILE" >/dev/null 2>&1 || true
  fi
  rm -rf "$LOG_DIR"
}

on_interrupt() {
  echo ""
  echo "Stopping all nodes..."
  cleanup
  echo "All nodes stopped."
  exit 0
}

trap cleanup EXIT
trap on_interrupt INT

start_coordinator() {
  echo "Starting Dora coordinator..."
  dora coordinator >"$COORDINATOR_LOG" 2>&1 &
  local pid=$!
  sleep 3
  if kill -0 "$pid" 2>/dev/null; then
    echo "   ✓ Coordinator is running (PID $pid)"
    PIDS+=("$pid")
    return 0
  fi

  echo "   ✗ Coordinator failed to start"
  cat "$COORDINATOR_LOG"
  return 1
}

start_daemon() {
  local name=$1
  shift
  local log_file="$LOG_DIR/${name}.log"

  echo "Starting Dora daemon for $name..."
  dora daemon "$@" >"$log_file" 2>&1 &
  local pid=$!
  sleep 2
  if kill -0 "$pid" 2>/dev/null; then
    echo "   ✓ Daemon $name is running (PID $pid)"
    PIDS+=("$pid")
    return 0
  fi

  echo "   ✗ Daemon $name failed to start"
  cat "$log_file"
  return 1
}

print_header() {
  echo "=== Distributed Dora Sensor Network (Local Simulation) ==="
  echo ""
  echo "This simulates 4 machines (edge1, edge2, edge3, cloud) on one PC"
  echo ""
}

check_version_alignment() {
  local cli_version
  cli_version=$(dora --version | awk '{print $2}')

  local py_version
  py_version=$("$PYTHON_BIN" - <<'PY'
import importlib
import sys

try:
    module = importlib.import_module("dora")
except ModuleNotFoundError:
    sys.exit(0)

version = getattr(module, "__version__", None)
if not version:
    sys.exit(0)

print(version)
PY
)

  if [ -z "$py_version" ]; then
    echo ""
    echo "WARNING: Python interpreter $PYTHON_BIN does not have the dora bindings installed."
    echo "Install them via '$PYTHON_BIN -m pip install dora-rs==$cli_version' or set PYTHON_BIN accordingly."
    return 1
  fi

  local cli_major=${cli_version%%.*}
  local cli_minor=${cli_version#*.}
  cli_minor=${cli_minor%%.*}
  local py_major=${py_version%%.*}
  local py_minor=${py_version#*.}
  py_minor=${py_minor%%.*}

  if [ "$cli_major" != "$py_major" ] || [ "$cli_minor" != "$py_minor" ]; then
    echo ""
    echo "Dora CLI version $cli_version does not match Python binding version $py_version."
    echo "Ensure both are aligned (e.g., run 'dora self update' or install 'dora-rs==$cli_major.$cli_minor.*' in $PYTHON_BIN)."
    return 1
  fi
}

print_header

if ! check_version_alignment; then
  exit 1
fi

echo "Checking for sandbox restrictions..."
if ! start_coordinator; then
  if grep -q "Operation not permitted" "$COORDINATOR_LOG"; then
    echo ""
    echo "The coordinator cannot bind to a TCP listener in this environment."
    echo "Your sandbox or OS policy is blocking network listeners."
    echo "Run this script outside the restricted sandbox (or request network access)"
    echo "to exercise the distributed deployment."
    exit 1
  fi
  exit 1
fi

sleep 1

echo ""
echo "Starting Dora daemons (simulating 4 machines):"
echo "  - edge1: Temperature sensor"
echo "  - edge2: Humidity sensor"
echo "  - edge3: Pressure sensor"
echo "  - cloud: Data aggregator"
echo ""

if ! start_daemon edge1 --machine-id edge1; then
  exit 1
fi

if ! start_daemon edge2 --machine-id edge2 --local-listen-port 53291; then
  exit 1
fi

if ! start_daemon edge3 --machine-id edge3 --local-listen-port 53292; then
  exit 1
fi

if ! start_daemon cloud --machine-id cloud --local-listen-port 53293; then
  exit 1
fi

echo ""
echo "Building dataflow..."
if ! dora build "$DATAFLOW_FILE"; then
  echo "ERROR: Failed to build dataflow"
  exit 1
fi

sleep 1

echo ""
echo "Starting dataflow..."
if ! dora start "$DATAFLOW_FILE"; then
  echo "ERROR: Failed to start dataflow"
  exit 1
fi

DATAFLOW_STARTED=1

echo ""
echo "All nodes started! Use 'dora logs <dataflow-id> <node-id>' in another terminal"
echo "to monitor output. Press Ctrl+C here to stop all nodes."
echo ""

wait
