# Release Notes

## v0.1.3 (2026-01-02)

### Smooth Motion Update

- Add quintic polynomial trajectory interpolation for fluid movements
- Replace jerky position control with torque-based PD control
- Auto-compute trajectory duration based on velocity and acceleration limits
- Add smooth sinusoidal gripper motion
- Movements now flow continuously without pause-and-run behavior

### New Features

- **TrajectoryGenerator class**: Quintic polynomial interpolation with zero velocity at endpoints
- **Torque control**: PD controller with tuned gains (Kp=100, Kd=20)
- **duration parameter**: Optional explicit trajectory duration in target_joints input

### New Configuration

- FRANKA_MAX_ACCELERATION: Maximum joint acceleration (default: 2.0 rad/s^2)

## v0.1.2 (2026-01-02)

### Initial Franka Panda Release

- DORA-RS driver node for Franka Panda robot arm (7-DOF)
- PyBullet physics simulation with built-in Franka URDF
- Support for joint space movements with joint limit validation
- Support for Cartesian space movements using inverse kinematics
- Gripper control (open/close/position)
- Environment variable configuration
- Example goal publisher node for testing
- Complete dataflow configuration
- Documentation and usage instructions

### Features

- **target_joints input**: Accept 7-joint angle targets as JSON
- **target_pose input**: Accept Cartesian pose targets with IK solver
- **gripper input**: Control gripper (open/close or width 0.0-0.04m)
- **command input**: Control commands (start, stop, home, get_joints, get_pose)
- **current_joints output**: Current 7-joint positions
- **current_pose output**: Current end-effector pose
- **status output**: Movement status tracking
- **error output**: Error reporting

### Configuration

- FRANKA_SIMULATION: Simulation mode (always true for PyBullet)
- FRANKA_GUI: Enable PyBullet visualization
- FRANKA_TIME_STEP: Simulation time step
- FRANKA_MAX_VELOCITY: Maximum joint velocity
- FRANKA_MAX_FORCE: Maximum joint force
