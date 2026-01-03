# DORA-RS UR5 Robot Driver

A DORA-RS driver node for controlling Universal Robots UR5 robot arm via RTDE protocol. This driver accepts target joint goals and Cartesian poses via DORA dataflow and controls the robot accordingly.

**Features:**
- Pure Python RTDE implementation (no native dependencies)
- Works on Apple Silicon (M1/M2/M3/M4) Macs
- Supports URSim Docker simulator and real UR5 robots
- Joint space (moveJ) and Cartesian (moveL) movements

## Prerequisites

### 1. URSim Docker (Simulator)

Start the Universal Robots simulator (URSim):

```bash
# For Apple Silicon (M1/M2/M3/M4) - requires Rosetta
docker run -d --name ursim \
  -e ROBOT_MODEL=UR5 \
  -p 5900:5900 \
  -p 6080:6080 \
  -p 29999:29999 \
  -p 30001-30004:30001-30004 \
  --platform=linux/amd64 \
  universalrobots/ursim_e-series

# For Intel Macs / Linux
docker run -d --name ursim \
  -e ROBOT_MODEL=UR5 \
  -p 5900:5900 \
  -p 6080:6080 \
  -p 29999:29999 \
  -p 30001-30004:30001-30004 \
  universalrobots/ursim_e-series
```

Access the simulator:
- VNC viewer: `localhost:5900` (password: `easybot`)
- Web browser: `http://localhost:6080/vnc.html`

**Important**: After starting URSim, you must complete the following via VNC:

1. **Power on the robot**: Click the red power button (bottom left) -> Click "ON" -> Click "START"
2. **Confirm Safety Configuration** (first time only):
   - Go to hamburger menu (top right) -> Settings -> System -> Safety
   - Click "Confirm Safety Configuration" at the bottom
   - Accept the default configuration
3. **Verify robot mode**: Robot should show "RUNNING" in green

### 2. Install DORA-RS

Install the DORA CLI (v0.3.11):

```bash
# Using cargo (recommended)
cargo install dora-cli --version 0.3.11

# Check version
dora --version
```

### 3. Install Python Dependencies

**IMPORTANT**: The dora-rs Python package version must match the dora-cli version exactly.

```bash
pip install -r requirements.txt

# Verify versions match
dora --version        # Should show 0.3.11
pip show dora-rs      # Should show 0.3.11
```

## Project Structure

```
ur5/
├── ur5_driver_node.py     # Main DORA driver node (pure Python RTDE)
├── goal_publisher_node.py # Example goal publisher for testing
├── test_connection.py     # Connection test script
├── dataflow.yml           # DORA dataflow configuration
├── requirements.txt       # Python dependencies
└── README.md
```

## Usage

### Quick Start

1. Start the URSim simulator (see Prerequisites)

2. Power on the robot in URSim via VNC

3. Run the DORA dataflow:

```bash
cd ur5
dora up
dora start dataflow.yml
```

4. Monitor the logs:

```bash
dora logs ur5_driver
```

5. Stop the dataflow:

```bash
dora stop
dora destroy
```

### Running Individual Nodes

For development/testing, run nodes directly:

```bash
# Terminal 1: Start DORA daemon
dora up

# Terminal 2: Start the dataflow
dora start dataflow.yml

# Or run standalone for testing
python ur5_driver_node.py
```

## Node Interfaces

### Inputs

| Input ID | Format | Description |
|----------|--------|-------------|
| `target_joints` | JSON | Target joint angles in radians |
| `target_pose` | JSON | Target Cartesian pose |
| `command` | String | Control commands |

#### target_joints Format

Simple array (6 joints: base, shoulder, elbow, wrist1, wrist2, wrist3):
```json
[0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]
```

With parameters:
```json
{
  "joints": [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0],
  "acceleration": 0.5,
  "velocity": 0.3,
  "wait": true
}
```

#### target_pose Format

```json
{
  "x": 0.3,
  "y": 0.0,
  "z": 0.4,
  "rx": 3.14,
  "ry": 0.0,
  "rz": 0.0
}
```

#### Commands

| Command | Description |
|---------|-------------|
| `start` | Connect/reconnect to robot |
| `stop` | Stop movement and disconnect |
| `home` | Move to home position |
| `get_joints` | Get current joint positions |
| `get_pose` | Get current TCP pose |

### Outputs

| Output ID | Format | Description |
|-----------|--------|-------------|
| `current_joints` | JSON array | Current joint positions in radians |
| `current_pose` | JSON dict | Current TCP pose (x, y, z, rx, ry, rz) |
| `status` | String | `idle`, `moving`, `completed`, `error`, `stopped` |
| `error` | JSON | Error details when status is `error` |

## Configuration

### Environment Variables

Set these in `dataflow.yml` or export before running:

| Variable | Default | Description |
|----------|---------|-------------|
| `UR5_IP` | `127.0.0.1` | Robot/simulator IP address |
| `UR5_ACCELERATION` | `0.5` | Default acceleration (rad/s^2 or m/s^2) |
| `UR5_VELOCITY` | `0.3` | Default velocity (rad/s or m/s) |

### Example: Real Robot Configuration

```yaml
nodes:
  - id: ur5_driver
    path: ur5_driver_node.py
    inputs:
      target_joints: planner/joints
    outputs:
      - current_joints
      - current_pose
      - status
      - error
    env:
      UR5_IP: "192.168.1.100"    # Your robot's IP
      UR5_ACCELERATION: "0.3"    # Slower for safety
      UR5_VELOCITY: "0.2"
```

## Integration Examples

### With Motion Planner

```yaml
nodes:
  - id: motion_planner
    path: your_planner.py
    inputs:
      goal: user_input/goal
    outputs:
      - joints

  - id: ur5_driver
    path: ur5_driver_node.py
    inputs:
      target_joints: motion_planner/joints
    outputs:
      - current_joints
      - status
```

### With Vision System

```yaml
nodes:
  - id: camera
    path: camera_node.py
    outputs:
      - image

  - id: vision
    path: vision_node.py
    inputs:
      image: camera/image
    outputs:
      - target_pose

  - id: ur5_driver
    path: ur5_driver_node.py
    inputs:
      target_pose: vision/target_pose
    outputs:
      - status
```

## Troubleshooting

### Connection Failed

1. Check if URSim is running:
   ```bash
   docker ps | grep ursim
   docker logs ursim
   ```

2. Verify the robot is powered on in URSim (connect via VNC to `localhost:5900`)

3. Check if RTDE port is accessible:
   ```bash
   nc -zv 127.0.0.1 30004
   ```

4. Check IP address in environment variables

### Movement Not Executing

1. Ensure robot is powered on and brakes released in URSim
2. Check if robot is in Remote Control mode (for real robots)
3. Check for protective stops in the teach pendant/URSim
4. Check for errors in output:
   ```bash
   dora logs ur5_driver
   ```

### DORA Not Starting

1. Ensure DORA daemon is running:
   ```bash
   dora up
   ```

2. Check dataflow syntax:
   ```bash
   dora check dataflow.yml
   ```

### Node Initialization Error

If you see `RuntimeError: Could not initiate node from environment variable` with `invalid type: map, expected a YAML tag starting with '!'`:

1. **Version mismatch** - The dora-rs Python package version must match dora-cli:
   ```bash
   # Check versions
   dora --version
   pip show dora-rs

   # Fix by installing matching version
   pip install dora-rs==0.3.11  # Match your CLI version
   ```

2. **Restart DORA daemon after fixing**:
   ```bash
   dora destroy
   dora up
   dora start dataflow.yml
   ```

### RTDE "Safety Setup Not Confirmed" Error

If you see "SafetySetup has not been confirmed yet" error:

1. Connect to URSim via VNC (`localhost:5900`)
2. Go to Settings (hamburger menu) -> System -> Safety
3. Click "Confirm Safety Configuration" at the bottom
4. Restart the driver

### Test Connection Script

Run the included test script to verify connectivity:

```bash
python test_connection.py
```

This will test:
- Dashboard Server (port 29999)
- RTDE Interface (port 30004)
- URScript Interface (port 30002)

## RTDE Protocol Notes

The UR RTDE (Real-Time Data Exchange) protocol provides:
- Real-time streaming of robot state data at 500Hz
- Low-latency command interface
- Synchronous and asynchronous motion control

Key differences from other interfaces:
- More reliable than the primary/secondary interfaces
- Lower latency than Dashboard Server
- Direct access to servo control

## License

MIT License
