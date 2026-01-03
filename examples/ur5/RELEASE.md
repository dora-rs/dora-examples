# Release Notes

## v0.1.5 (2026-01-02)

### Pure Python RTDE Implementation

- Replaced ur_rtde C++ library with pure Python implementation
- Full Apple Silicon (M1/M2/M3/M4) Mac support
- No native dependencies required
- Added test_connection.py script for connectivity testing
- Updated documentation with safety configuration instructions

## v0.1.4 (2026-01-02)

### Initial UR5 Robot Arm Release

- DORA-RS driver node for Universal Robots UR5 robot arm (6-DOF)
- UR RTDE protocol support for real-time robot control
- URSim Docker simulator support (with --platform=linux/amd64 for Apple Silicon)
- Support for joint space movements (moveJ)
- Support for Cartesian space movements (moveL)
- Environment variable configuration
- Example goal publisher node for testing
- Complete dataflow configuration
- Documentation with URSim setup instructions

### Features

- **target_joints input**: Accept 6-joint angle targets as JSON
- **target_pose input**: Accept Cartesian pose targets for linear movements
- **command input**: Control commands (start, stop, home, get_joints, get_pose)
- **current_joints output**: Current 6-joint positions
- **current_pose output**: Current TCP pose
- **status output**: Movement status tracking
- **error output**: Error reporting

### Configuration

- UR5_IP: Robot/simulator IP address (default: 127.0.0.1)
- UR5_ACCELERATION: Default acceleration in rad/s^2 (default: 0.5)
- UR5_VELOCITY: Default velocity in rad/s (default: 0.3)
