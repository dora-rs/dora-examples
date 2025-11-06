# Python Distributed Dora Sensor Network

This example demonstrates **Dora's built-in distributed deployment capabilities** using the coordinator-daemon architecture with automatic Zenoh routing for cross-network communication.

## Key Features

✅ **Native Dora Distribution**: Uses `_unstable_deploy.machine` tags
✅ **Coordinator-Daemon Architecture**: Standard Dora distributed pattern
✅ **Automatic Zenoh Routing**: Cross-network communication handled by Dora
✅ **No Manual Zenoh Setup**: Dora manages Zenoh internally
✅ **Machine-Based Deployment**: Each node assigned to specific machine ID

## Architecture

```
                   Dora Coordinator
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    Daemon (edge1)   Daemon (edge2)   Daemon (edge3)   Daemon (cloud)
         │                │                │                 │
    sensor-temp     sensor-humidity  sensor-pressure   cloud-aggregator
    (temperature)     (humidity)      (pressure)       (aggregates all)
```

**Zenoh Integration**: When nodes are on different machines, Dora automatically uses its built-in Zenoh backend to route messages. Data flows through Zenoh topics like:
```
dora/default/{dataflow_id}/output/sensor-temp/data
dora/default/{dataflow_id}/output/sensor-humidity/data
dora/default/{dataflow_id}/output/sensor-pressure/data
```

## Dataflow Configuration

The `dataflow.yml` uses Dora's `_unstable_deploy` feature:

```yaml
nodes:
  - id: sensor-temp
    _unstable_deploy:
      machine: edge1      # Runs on daemon with --machine-id edge1
      working_dir: /Users/username/python-distributed-zenoh
    path: python3
    args: sensor_node.py sensor_temp temperature
    outputs:
      - data

  - id: cloud-aggregator
    _unstable_deploy:
      machine: cloud      # Runs on daemon with --machine-id cloud
      working_dir: /Users/username/python-distributed-zenoh
    inputs:
      temp_data: sensor-temp/data
      humidity_data: sensor-humidity/data
      pressure_data: sensor-pressure/data
```

**Important**: The `working_dir` parameter tells each daemon where to find the Python scripts. For real distributed deployments, ensure the scripts exist at this path on each target machine.

## Installation

### On All Machines

```bash
# Install dora-rs (includes CLI and Python API)
pip install dora-rs

# Optional: Install Zenoh tools for cross-network deployments
# (requires Rust/Cargo)
cargo install zenoh --features unstable
```

### AWS EC2 Security Group Configuration (For Cross-Network)

If deploying to EC2, configure security group to allow:
- **TCP 7447** - Zenoh router (from 0.0.0.0/0)
- **TCP 53290** - Dora coordinator (from 0.0.0.0/0)

In AWS Console: EC2 → Security Groups → Add Inbound Rules

## Running on ONE Machine (Simulation)

Simulate distributed deployment with multiple daemons on one PC:

### Manual Steps

**Terminal 1 - Coordinator:**
```bash
dora coordinator
```

**Terminal 2 - Edge Device 1 (Temperature Sensor):**
```bash
dora daemon --machine-id edge1
```

**Terminal 3 - Edge Device 2 (Humidity Sensor):**
```bash
dora daemon --machine-id edge2 --local-listen-port 53291
```

**Terminal 4 - Edge Device 3 (Pressure Sensor):**
```bash
dora daemon --machine-id edge3 --local-listen-port 53292
```

**Terminal 5 - Cloud Server:**
```bash
dora daemon --machine-id cloud --local-listen-port 53293
```

**Terminal 6 - Start Dataflow:**
```bash
dora build dataflow.yml
dora start dataflow.yml
```

## Running on real distribution

### Same Network (WiFi/LAN)

All machines in the same network can auto-discover via Zenoh multicast.

**On Cloud Server (e.g., 192.168.1.100):**
```bash
# Start coordinator
dora coordinator
```

**On Each Edge Device:**
```bash
# Edge device 1
dora daemon --coordinator-addr 192.168.1.100 --machine-id edge1

# Edge device 2
dora daemon --coordinator-addr 192.168.1.100 --machine-id edge2

# Edge device 3
dora daemon --coordinator-addr 192.168.1.100 --machine-id edge3
```

**On Cloud Server:**
```bash
# This daemon runs the cloud-aggregator node
dora daemon --machine-id cloud

# Start the dataflow
dora start dataflow.yml
```

### Different Networks (Cross-Network) - AWS EC2 Example

When machines are in different networks (behind NAT/firewalls), use Zenoh routers. This example shows connecting a home PC to AWS EC2.

#### Prerequisites

1. **On Both Machines:**
```bash
pip install dora-rs
```

2. **Copy Files to EC2 (`~/dora-distributed/`):**
   - `sensor_node.py`
   - `cloud_node.py`
   - `dataflow_distributed.yml`
   - `zenoh_config.json5`

3. **Update `dataflow_distributed.yml` paths:**
   - Edge device: Set `working_dir` to your local path (e.g., `/Users/username/python-distributed-zenoh` for Mac, `/home/username/dora-distributed` for Linux)
   - Cloud: Set `working_dir` to EC2 path (e.g., `/home/ubuntu/dora-distributed`)

Example configuration:
```yaml
nodes:
  - id: sensor-temp
    _unstable_deploy:
      machine: edge1
      working_dir: /Users/username/python-distributed-zenoh  # Mac path
    path: python3
    args: sensor_node.py sensor_temp temperature
    inputs:
      tick: dora/timer/millis/1000
    outputs:
      - data

  - id: cloud-aggregator
    _unstable_deploy:
      machine: cloud
      working_dir: /home/ubuntu/dora-distributed  # EC2 path
    path: python3
    args: cloud_node.py
    inputs:
      temp_data: sensor-temp/data
```

#### Setup Zenoh Config

Create `zenoh_config.json5` (on both machines):
```json5
{
  mode: "client",
  connect: {
    endpoints: ["tcp/YOUR_EC2_IP:7447"]  // Replace with your EC2 public IP
  },
  listen: {
    endpoints: []
  }
}
```

**Key Settings:**
- `mode: "client"` - Makes dora daemon a Zenoh client (not a router)
- `listen: { endpoints: [] }` - Prevents port conflicts with zenohd router
- Replace `YOUR_EC2_IP` with your actual EC2 public IP address

#### On EC2 (Cloud Server)

**Terminal 1 - Start Zenoh Router:**
```bash
zenohd --listen tcp/0.0.0.0:7447
```

**Terminal 2 - Start Dora Coordinator:**
```bash
cd ~/dora-distributed
dora coordinator
```

**Terminal 3 - Start Cloud Daemon:**
```bash
cd ~/dora-distributed
export ZENOH_CONFIG=zenoh_config.json5
dora daemon --machine-id cloud
```

You should see:
```
INFO dora_daemon::coordinator: Connected to dora-coordinator at 127.0.0.1:53290
```

#### On Your PC/Mac (Edge Device)

**Terminal 1 - Start Edge Daemon:**
```bash
cd /path/to/dora-examples/examples/python-distributed-zenoh
export ZENOH_CONFIG=zenoh_config.json5
dora daemon --coordinator-addr YOUR_EC2_IP --machine-id edge1
```

You should see:
```
INFO dora_daemon::coordinator: Connected to dora-coordinator at YOUR_EC2_IP:53290
```

#### Start the Dataflow (From EC2)

**Terminal 4 on EC2:**
```bash
cd ~/dora-distributed

# Verify both daemons are connected
dora list

# Build the dataflow
dora build dataflow_distributed.yml

# Start the dataflow (controls both machines)
dora start dataflow_distributed.yml
```

#### Expected Output

**On EC2 (Terminal 4) - Cloud Aggregator:**
```
dataflow start triggered: 019a5637-3863-7f52-aac5-df670c2a7132
attaching to dataflow (use `--detach` to run in background)

cloud-aggregator on daemon `cloud`: INFO   daemon    node is ready
cloud-aggregator on daemon `cloud`: stdout    === Cloud Aggregator Node ===
cloud-aggregator on daemon `cloud`: stdout    Receiving data via Dora's distributed Zenoh routing
cloud-aggregator on daemon `cloud`: stdout    
cloud-aggregator on daemon `cloud`: stdout    Cloud aggregator started! Press Ctrl+C to stop
cloud-aggregator on daemon `cloud`: stdout    
cloud-aggregator on daemon `cloud`: stdout    >> [00001] Received from sensor_temp: temperature=23.45celsius
cloud-aggregator on daemon `cloud`: stdout    >> [00002] Received from sensor_temp: temperature=24.12celsius
cloud-aggregator on daemon `cloud`: stdout    >> [00003] Received from sensor_temp: temperature=22.89celsius
cloud-aggregator on daemon `cloud`: stdout    
cloud-aggregator on daemon `cloud`: stdout    ======================================================================
cloud-aggregator on daemon `cloud`: stdout    Cloud Aggregator Summary - Total Messages: 10
cloud-aggregator on daemon `cloud`: stdout    Active Sensors: 1
cloud-aggregator on daemon `cloud`: stdout    ======================================================================
cloud-aggregator on daemon `cloud`: stdout    🟢 ACTIVE | sensor_temp     | temperature  |   24.12 celsius  | Count:    10
cloud-aggregator on daemon `cloud`: stdout    ======================================================================
```

**On Your PC/Mac (Terminal 1) - Edge Daemon:**
```
INFO dora_daemon::coordinator: Connected to dora-coordinator at YOUR_EC2_IP:53290
WARN run_inner: dora_daemon: Daemon took 158ms for handling event
```

The sensor node runs silently in the background, sending temperature data every second through the Zenoh router to EC2.

#### Architecture Flow

```
Your PC/Mac (edge1)          EC2 Cloud (YOUR_EC2_IP)
┌─────────────────┐           ┌─────────────────────────┐
│ sensor-temp     │           │ zenohd :7447 (router)   │
│ (publishes)     │──Zenoh──▶│                         │
│                 │           │ dora coordinator :53290 │
│ dora daemon     │◀─Control─│                         │
│ (edge1)         │           │ dora daemon (cloud)     │
└─────────────────┘           │                         │
                              │ cloud-aggregator        │
                              │ (receives & aggregates) │
                              └─────────────────────────┘
```

#### Troubleshooting Cross-Network Setup

**"Connection refused" when starting daemon:**
- Verify EC2 public IP is correct in `--coordinator-addr`
- Check EC2 security group allows TCP port 53290 (coordinator)
- Ensure coordinator is running on EC2

**"Operation not supported (os error 45)" on Mac:**
- Update `dataflow_distributed.yml` with correct Mac path in `working_dir`
- Mac uses `/Users/...`, not `/home/...`

**"Address already in use" for port 7447:**
- Update `zenoh_config.json5` with `mode: "client"` and `listen: { endpoints: [] }`
- Only the `zenohd` router should listen on 7447

**Zenoh connection issues:**
- Verify EC2 security group allows TCP port 7447 (Zenoh router) and TCP port 53290 (coordinator)
- Test Zenoh connectivity: `z_pub --connect tcp/<EC2_IP>:7447 --key test`
- On EC2, verify services are listening: `netstat -tuln | grep -E '7447|53290'`

## Expected Output

**Sensor Node (edge1):**
```
=== Sensor Node: sensor_temp ===
Type: temperature
Sensor node sensor_temp started!
Data will be automatically routed via Dora's Zenoh integration
Press Ctrl+C to stop

[0001] Sent: temperature=23.45celsius
[0002] Sent: temperature=24.12celsius
[0003] Sent: temperature=22.89celsius
...
```

**Cloud Aggregator:**
```
=== Cloud Aggregator Node ===
Receiving data via Dora's distributed Zenoh routing

Cloud aggregator started! Press Ctrl+C to stop

>> [00001] Received from sensor_temp: temperature=23.45celsius
>> [00002] Received from sensor_humidity: humidity=65.32percent
>> [00003] Received from sensor_temp: temperature=24.12celsius
>> [00004] Received from sensor_pressure: pressure=1013.45hPa

======================================================================
Cloud Aggregator Summary - Total Messages: 15
Active Sensors: 3
======================================================================
🟢 ACTIVE | sensor_temp     | temperature  |   24.12 celsius  | Count:     5
🟢 ACTIVE | sensor_humidity | humidity     |   65.32 percent  | Count:     4
🟢 ACTIVE | sensor_pressure | pressure     | 1013.45 hPa      | Count:     3
======================================================================
```

## How Dora's Distribution Works

1. **Coordinator**: Central manager that tracks all daemons and dataflows
2. **Daemons**: One per machine, identified by `--machine-id`
3. **Machine Assignment**: Nodes use `_unstable_deploy.machine` in YAML
4. **Automatic Routing**:
   - Same machine: Direct communication
   - Same network: Zenoh multicast auto-discovery
   - Different networks: Zenoh routers (configured via `ZENOH_CONFIG`)

## Deployment Checklist

- [ ] Copy Python scripts to each target machine
- [ ] Install `dora-rs` on all machines: `pip install dora-rs`
- [ ] Start coordinator on accessible server
- [ ] Start daemon on each machine with unique `--machine-id`
- [ ] Machine IDs in YAML must match daemon `--machine-id`
- [ ] For cross-network: Set up Zenoh routers and `ZENOH_CONFIG`

## Troubleshooting

**"No such file or directory" error:**
- Ensure `working_dir` is set in `_unstable_deploy` section
- Verify Python scripts exist at the working directory path
- For distributed setups, copy scripts to the same path on all machines

**Nodes not connecting:**
- Check coordinator IP is accessible from all machines
- Verify machine IDs in YAML match daemon `--machine-id`
- Check firewall allows Zenoh ports (default: UDP 7447)

**No data received:**
- Verify nodes are running: `dora list`
- Check logs: `dora logs sensor-temp`, `dora logs cloud-aggregator`
- Ensure all Python scripts are present on their target machines

**Cross-network issues:**
- Verify Zenoh router (`zenohd`) is running
- Check `ZENOH_CONFIG` points to correct router
- Test Zenoh connectivity: `z_ping`

**Zenoh warnings (tcp/[::]:5456 already in use):**
- Safe to ignore when running multiple daemons locally
- Daemons will automatically retry with alternative configuration

## Zenoh Topic Structure

Dora uses this Zenoh topic naming:
```
dora/{network_id}/{dataflow_id}/output/{node_id}/{output_id}
```

Example:
```
dora/default/019a41c7-0718-75ca-82fe-66ad9b289b5b/output/sensor-temp/data
```

You can monitor these topics directly with Zenoh tools:
```bash
# Subscribe to all dora topics
z_sub 'dora/**'
```

## Testing Network Connectivity

Before running dora-zenoh, verify Zenoh connectivity works:

**Terminal A (on edge or EC2):**
```bash
z_sub --connect tcp/YOUR_EC2_IP:7447 --key demo/test
```

**Terminal B (on another machine):**
```bash
echo "🔥 connected!" | z_pub --connect tcp/YOUR_EC2_IP:7447 --key demo/test
```

**Expected output on Terminal A:**
```
Received (key='demo/test'): 🔥 connected!
```

If this works, your network is configured correctly. If dora still has issues, check the dora-specific troubleshooting above.


## References

- [Dora Multiple Daemons Example](https://github.com/dora-rs/dora/tree/main/examples/multiple-daemons)
- [Zenoh Documentation](https://zenoh.io/docs/)
- [Dora Documentation](https://github.com/dora-rs/dora)
