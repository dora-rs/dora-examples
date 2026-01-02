# Release Notes

## v0.1.1 (2025-12-31)

### Bug Fixes

- Fixed dataflow.yml format for DORA-RS 0.3.11 compatibility
- Pinned dora-rs Python package version to match CLI (0.3.11)
- Added version mismatch troubleshooting to README

### Important

The dora-rs Python package version must exactly match the dora-cli version.
See README troubleshooting section for details.

## v0.1.0 (2025-12-31)

### Initial Release

- DORA-RS driver node for Lebai LM3 robot arm
- Support for joint space movements (movej)
- Support for Cartesian space movements (movel)
- Environment variable configuration
- Example goal publisher node for testing
- Complete dataflow configuration
- Documentation and usage instructions

### Features

- **target_joints input**: Accept joint angle targets as JSON
- **target_pose input**: Accept Cartesian pose targets as JSON
- **command input**: Control commands (start, stop, home, get_joints)
- **current_joints output**: Current joint positions
- **status output**: Movement status tracking
- **error output**: Error reporting

### Configuration

- LEBAI_IP: Robot IP address
- LEBAI_SIMULATION: Simulation mode toggle
- LEBAI_ACCELERATION: Default acceleration
- LEBAI_VELOCITY: Default velocity
