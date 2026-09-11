# Terminal HUD User Guide

DockPulse provides a keyboard-driven terminal dashboard designed for fast microservice monitoring.

## Launching the Interface

Run DockPulse from any terminal:

```bash
dockpulse
```

To run with simulated microservice containers:

```bash
dockpulse --demo
```

## Screen Layout

1. **Header Bar**: Displays Docker engine version, API version, connection endpoint, and counts for running, paused, and stopped containers.
2. **Container Panel (Left)**: Shows containers grouped by Compose project. Press `Up` and `Down` to navigate, `Enter` to expand or collapse Compose groups or open the container command runner.
3. **Telemetry Panel (Top Right)**: Displays real-time rolling sparkline charts for CPU usage and memory consumption, plus network transmission and block disk metrics.
4. **Log Streamer (Bottom Right)**: Displays live tail logs with color-coded stdout and stderr lines.

## Commands and Shortcuts

- `Up` / `Down`: Move selection in container tree.
- `r`: Restart selected container.
- `s`: Stop selected container.
- `p`: Pause or resume selected container.
- `x`: Remove stopped container.
- `d`: Open detailed JSON and configuration modal.
- `Enter`: Open interactive shell or command runner.
- `/`: Search / filter container names or log lines.
- `Space`: Pause or resume log autoscroll.
- `c`: Clear log display buffer.
- `?`: Display help modal with keybindings.
- `q`: Quit DockPulse.
