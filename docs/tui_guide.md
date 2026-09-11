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

![DockPulse Terminal HUD](images/screenshot_main.png)

1. **Header Bar**: Displays Docker engine version, API version, connection endpoint, reclaimable disk space, and counts for running, paused, and stopped containers.
2. **Container Panel (Left)**: Shows containers grouped by Compose project. Press `Up` and `Down` to navigate, `Enter` to expand or collapse Compose groups or open the container command runner. Filter by typing `/`.
3. **Telemetry Panel (Top Right)**: Displays real-time rolling sparkline charts for CPU usage and memory consumption, plus network transmission, block disk metrics, and watchdog anomaly badges (`💀 OOMKilled`, `⚠️ CrashLoop`).
4. **Log Streamer (Bottom Right)**: Displays live tail logs with color-coded stdout and stderr lines, ISO timestamp toggles, severity filters, and file export options.

## Commands and Shortcuts

### Container and Stack Controls
- `Up` / `Down`: Move selection in container tree.
- `r`: Restart selected container.
- `s`: Stop selected container.
- `p`: Pause or resume selected container.
- `x`: Remove stopped container.
- `Shift+R`: Restart all containers in the selected Compose project.
- `Shift+S`: Stop all containers in the selected Compose project.

### Productivity and Quick Actions
- `o`: Open published HTTP/HTTPS web port directly in your default browser.
- `y`: Copy connection string or `docker exec` command to the system clipboard.
- `e` / `Enter`: Open interactive shell or command runner.
- `d`: Open detailed JSON and configuration modal.
- `i`: Open Docker images manager (view image tags, size, and prune dangling images).
- `v`: Open Docker volumes manager (view volumes, driver, and remove unused volumes).

### Logs and Monitoring
- `t`: Toggle ISO 8601 timestamps prefix on log entries.
- `l`: Cycle log severity filter (`ALL` -> `ERROR` -> `WARN` -> `INFO` -> `DEBUG`).
- `Ctrl+S`: Export log buffer to a timestamped file on disk.
- `/`: Search / filter container names or log lines.
- `Space`: Pause or resume log autoscroll.
- `c`: Clear log display buffer.

### Visuals and Help
- `Shift+T`: Open palette switcher modal (Slate, Tokyo Night, Catppuccin Mocha, Dracula, Nord).
- `?`: Display help modal with all keybindings.
- `q`: Quit DockPulse.

## Configuration File

DockPulse can be customized via `dockpulse.toml` in your current working directory or at `~/.config/dockpulse/dockpulse.toml`:

```toml
[ui]
theme = "tokyo_night"      # "slate", "tokyo_night", "catppuccin", "dracula", "nord"
show_timestamps = true
log_level = "ALL"          # "ALL", "ERROR", "WARN", "INFO", "DEBUG"

[shell]
preferred_shell = "/bin/sh"
```
