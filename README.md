# DockPulse

High-speed, keyboard-driven terminal dashboard and CLI tool for Docker and Docker Compose. DockPulse connects directly to the Docker Engine socket without external daemons, groups containers by Compose project, renders live rolling resource graphs, tails multiplexed logs, and provides container lifecycle controls from your keyboard.

[![CI](https://github.com/alexandrmotologa/dockpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/alexandrmotologa/dockpulse/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

---

## Features

- **Direct socket transport**: Connects to Windows Named Pipes (`\\.\pipe\docker_engine`), Unix Domain Sockets (`/var/run/docker.sock`), or remote TCP endpoints without requiring third-party bridge agents.
- **Compose project hierarchy**: Groups microservice containers by `com.docker.compose.project`, displaying status badges, service names, and replica counts.
- **Live resource sparklines**: Rolling metrics for CPU percentage across cores, memory RSS, network I/O rates, and block storage operations.
- **Demultiplexed log streaming**: Reads Docker 8-byte framing headers, separating stdout and stderr streams with timestamp normalization and search filtering (`/`).
- **One-key container actions**: Restart (`r`), stop (`s`), pause/unpause (`p`), or remove (`x`) containers directly from the HUD.
- **Integrated demo mode**: Explore the entire terminal dashboard with simulated multi-service topologies without needing a running Docker daemon (`dockpulse --demo`).

---

## Installation

### Using uv (recommended)

```bash
uv tool install dockpulse
```

Or run directly without installing:

```bash
uvx dockpulse
```

### Using pip

```bash
pip install dockpulse
```

---

## Quick Start

Launch the interactive terminal HUD:

```bash
dockpulse
```

Try the HUD in demo mode:

```bash
dockpulse --demo
```

Check Docker engine connection and socket diagnostics:

```bash
dockpulse check
```

---

## CLI Commands

DockPulse includes CLI subcommands for common operational tasks:

```bash
# Launch the interactive terminal HUD (default)
dockpulse hud

# List containers grouped by Compose project in a compact table
dockpulse ps

# Display snapshot resource statistics for active containers
dockpulse stats

# Stream demultiplexed logs for a specific container
dockpulse logs <container-name-or-id>

# Safely prune unused containers, networks, and dangling images
dockpulse prune --dry-run
```

---

## Keybindings

| Key | Action |
|---|---|
| `Up` / `Down` | Navigate container tree |
| `r` | Restart highlighted container |
| `s` | Stop highlighted container |
| `p` | Pause or unpause highlighted container |
| `x` | Remove stopped container |
| `Enter` | Open container shell / command runner |
| `d` | Inspect container details (ports, mounts, env) |
| `/` | Filter containers or search live logs |
| `Space` | Pause or resume log scrolling |
| `c` | Clear log buffer |
| `?` | Show help modal |
| `q` | Exit HUD |

---

## Architecture Overview

```
+-------------------------------------------------------------+
|                        DockPulse HUD                        |
|   +---------------------+   +---------------------------+   |
|   | Container Tree      |   | Live Resource Sparklines  |   |
|   | (Grouped by Compose)|   | (CPU %, RAM, Net, Disk)   |   |
|   +---------------------+   +---------------------------+   |
|   | Status Indicators   |   | Demultiplexed Log Streamer|   |
|   +---------------------+   +---------------------------+   |
+-------------------------------------------------------------+
                              |
                     Docker REST v1.43
                              |
        +---------------------+---------------------+
        |                                           |
Windows Named Pipe                         Unix Domain Socket
(\\.\pipe\docker_engine)                   (/var/run/docker.sock)
```

See [docs/architecture.md](docs/architecture.md) and [docs/socket_transport.md](docs/socket_transport.md) for detailed technical specifications.

---

## Development

Prerequisites: Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
# Clone the repository
git clone https://github.com/alexandrmotologa/dockpulse.git
cd dockpulse

# Create virtual environment and install dependencies
uv sync --all-extras --dev

# Run tests
uv run pytest -v

# Run lint and formatting checks
uv run ruff check .
uv run ruff format --check .
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
