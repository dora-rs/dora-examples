# DORA-RS SO-101 Follower Arm Driver (MuJoCo Simulation)

A DORA-RS driver node for controlling the SO-101 follower arm using MuJoCo physics simulation. Uses the official SO-ARM100 model from [TheRobotStudio](https://github.com/TheRobotStudio/SO-ARM100).

The SO-101 is a 6-DOF low-cost robot arm commonly used in the LeRobot teleoperation project.

## Features

- Official SO-ARM100 MuJoCo model with accurate CAD meshes
- 6-DOF control (5 arm joints + gripper)
- Smooth quintic trajectory interpolation
- OpenCV-based visualization (works on macOS without mjpython)
- DORA dataflow integration

## Prerequisites

### 1. Install DORA-RS

Install the DORA CLI:

```bash
# Using cargo (recommended)
cargo install dora-cli

# Check version
dora --version
```

### 2. Install Python Dependencies

**IMPORTANT**: The dora-rs Python package version must match the dora-cli version exactly.

```bash
pip install -r requirements.txt

# Verify versions match
dora --version        # Note the version
pip show dora-rs      # Should match CLI version
```

## Project Structure

```
so101/
├── so101_driver_node.py   # Main DORA driver node with MuJoCo simulation
├── goal_publisher_node.py # Example goal publisher for testing
├── dataflow.yml           # DORA dataflow configuration
├── requirements.txt       # Python dependencies
├── so101_new_calib.xml    # MuJoCo model (from SO-ARM100)
├── scene.xml              # Scene configuration
├── assets/                # STL mesh files
├── README.md
└── RELEASE.md
```

## Usage

### Quick Start

1. Run the DORA dataflow:

```bash
cd so101
dora up
dora start dataflow.yml
```

2. Monitor the logs:

```bash
dora logs so101_driver
```

3. Stop the dataflow:

```bash
dora stop
dora destroy
```

## Node Interfaces

### Inputs

| Input ID | Format | Description |
|----------|--------|-------------|
| `target_joints` | JSON | Target joint angles for all 6 joints |
| `command` | String | Control commands |

#### target_joints Format

Simple array (6 values):
```json
[0.0, 0.5, -0.8, 0.3, 0.0, 1.0]
```

With parameters:
```json
{
  "joints": [0.0, 0.5, -0.8, 0.3, 0.0, 1.0],
  "duration": 1.5
}
```

#### Joint Descriptions

| Index | Name | Description | Range (rad) |
|-------|------|-------------|-------------|
| 0 | shoulder_pan | Base rotation | -1.92 to 1.92 |
| 1 | shoulder_lift | Shoulder pitch | -1.75 to 1.75 |
| 2 | elbow_flex | Elbow pitch | -1.69 to 1.69 |
| 3 | wrist_flex | Wrist pitch | -1.66 to 1.66 |
| 4 | wrist_roll | Wrist roll | -2.74 to 2.84 |
| 5 | gripper | Gripper | -0.17 to 1.75 |

#### Commands

| Command | Description |
|---------|-------------|
| `start` | Initialize simulation |
| `stop` | Close simulation |
| `home` | Move to home position |
| `get_joints` | Get current joint positions |

### Outputs

| Output ID | Format | Description |
|-----------|--------|-------------|
| `current_joints` | JSON array | Current joint positions |
| `status` | String | `idle`, `moving`, `completed`, `error`, `stopped` |
| `error` | JSON | Error details when status is `error` |

## Configuration

### Environment Variables

Set these in `dataflow.yml` or export before running:

| Variable | Default | Description |
|----------|---------|-------------|
| `SO101_SHOW_VIEWER` | `true` | Show OpenCV visualization window |
| `SO101_TIMESTEP` | `0.002` | Simulation timestep (seconds) |
| `SO101_CONTROL_FREQ` | `50` | Control loop frequency (Hz) |

## Integration Examples

### With LeRobot Teleoperation

```yaml
nodes:
  - id: leader_arm
    path: leader_arm_node.py
    outputs:
      - joint_positions

  - id: so101_driver
    path: so101_driver_node.py
    inputs:
      target_joints: leader_arm/joint_positions
    outputs:
      - current_joints
      - status
```

### With Policy Inference

```yaml
nodes:
  - id: camera
    path: camera_node.py
    outputs:
      - image

  - id: policy
    path: policy_node.py
    inputs:
      image: camera/image
      current_joints: so101_driver/current_joints
    outputs:
      - action

  - id: so101_driver
    path: so101_driver_node.py
    inputs:
      target_joints: policy/action
    outputs:
      - current_joints
      - status
```

## Troubleshooting

### Viewer Not Showing

The driver uses OpenCV for rendering, which works with regular Python on macOS:

```yaml
# In dataflow.yml - ensure viewer is enabled
env:
  SO101_SHOW_VIEWER: "true"
```

### Model Not Found

Ensure all files are present:
- `so101_new_calib.xml` - Main model file
- `assets/` directory with all STL meshes

### DORA Not Starting

1. Ensure DORA daemon is running:
   ```bash
   dora up
   ```

2. Check dataflow syntax:
   ```bash
   dora check dataflow.yml
   ```

## Model Credits

The SO-101 model is from the [SO-ARM100 project](https://github.com/TheRobotStudio/SO-ARM100) by TheRobotStudio, generated using the onshape-to-robot plugin.

## License

MIT License
