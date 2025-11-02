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
      working_dir: /Users/nupylot/Public/dora-examples/examples/python-distributed-zenoh
    path: python3
    args: sensor_node.py sensor_temp temperature
    outputs:
      - data

  - id: cloud-aggregator
    _unstable_deploy:
      machine: cloud      # Runs on daemon with --machine-id cloud
      working_dir: /Users/nupylot/Public/dora-examples/examples/python-distributed-zenoh
    inputs:
      temp_data: sensor-temp/data
      humidity_data: sensor-humidity/data
      pressure_data: sensor-pressure/data
```

**Important**: The `working_dir` parameter tells each daemon where to find the Python scripts. For real distributed deployments, ensure the scripts exist at this path on each target machine.

## Installation

```bash
pip install -r requirements.txt
```

## Running on ONE Machine (Simulation)

Simulate distributed deployment with multiple daemons on one PC:

### Automated (Recommended)
```bash
./run_local.sh
```

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

## Running on MULTIPLE Machines (Real Distribution)

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
dora start --coordinator-addr 192.168.1.100 dataflow.yml
```

### Different Networks (Cross-Network)

When machines are in different networks (behind NAT/firewalls), use Zenoh routers.

**1. Set up Zenoh Router on each network:**

Create `zenoh_config.json5`:
```json5
{
  connect: {
    endpoints: ["tcp/<ROUTER_IP>:7447"]
  }
}
```

**2. Start Zenoh Router:**
```bash
zenohd -l tcp/0.0.0.0:7447
```

**3. Start Dora Daemons with Zenoh Config:**
```bash
# On each machine
ZENOH_CONFIG=zenoh_config.json5 dora daemon --coordinator-addr <COORDINATOR_IP> --machine-id edge1
```

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

## References

- [Dora Multiple Daemons Example](https://github.com/dora-rs/dora/tree/main/examples/multiple-daemons)
- [Zenoh Documentation](https://zenoh.io/docs/)
- [Dora Documentation](https://github.com/dora-rs/dora)
