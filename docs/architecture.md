# Architecture

DockPulse connects directly to the Docker Engine REST API without running background daemon proxies or heavy runtime dependencies.

## Design Goals

1. **Low latency**: Sub-50ms startup time, minimal CPU footprint when idling in background.
2. **Native socket access**: Direct communication with Windows Named Pipes and Unix Domain Sockets.
3. **Async stream processing**: Multiplexed log parsing and rolling metrics calculation without blocking the main TUI render loop.
4. **Compose awareness**: First-class grouping and aggregated health calculation based on Compose labels.

## System Components

```
+------------------------------------------------------------------------+
|                             TUI Layer                                  |
|  - Textual App (DockPulseHUD)                                          |
|  - Container Tree Widget, Sparkline Widget, Log Streamer Widget        |
|  - Modals: DetailModal, ShellModal, PruneModal, HelpModal,             |
|            ImagesModal, VolumesModal, ThemeModal                       |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
|                             Core Layer                                 |
|  - ContainerModel & ComposeProject (Pydantic v2, OOM/CrashLoop check)  |
|  - StatsStreamer (Delta CPU %, memory RSS, network I/O, block I/O)     |
|  - SparklineBuffer (Rolling time-series, Unicode sparkline rendering)  |
|  - LogMultiplexer (8-byte header demuxer, level filter, export)        |
|  - ThemeEngine (Slate, Tokyo Night, Catppuccin, Dracula, Nord)         |
|  - ClipboardHelper (Cross-platform clipboard provider)                 |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
|                            Client Layer                                |
|  - DockerApiClient (Asynchronous HTTP REST v1.43 client)              |
|  - SocketTransport (Windows Named Pipe, Unix Domain Socket, TCP)       |
|  - MockTransport (In-memory simulation for demo mode & tests)          |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
|                           Docker Engine                                |
|  - Windows Named Pipe: \\.\pipe\docker_engine                          |
|  - Unix Domain Socket: /var/run/docker.sock                            |
+------------------------------------------------------------------------+
```

## Data Flow

1. **Initialization**: On startup, `dockpulse` checks for configured socket paths (from `DOCKER_HOST` or platform defaults). If `--demo` is set or the socket is unavailable, it initializes `MockTransport`.
2. **Container Discovery**: The client requests `/v1.43/containers/json?all=1`. The core layer parses the payload into `ContainerModel` instances and groups them by Compose project.
3. **Telemetry Streaming**: When a container is selected, background asyncio tasks stream metrics from `/containers/{id}/stats` and logs from `/containers/{id}/logs?follow=1`.
4. **Event Reactivity**: The client maintains a long-lived connection to `/v1.43/events`. Container lifecycle changes (start, stop, health status) update the state without requiring full poll cycles.
