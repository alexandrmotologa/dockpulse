"""In-memory simulated Docker daemon transport for testing and demo mode."""

import asyncio
import copy
import json
import math
import struct
import time
from typing import Any

import httpx

from dockpulse.core.mock_data import MOCK_CONTAINERS_RAW, MOCK_LOG_SAMPLES


class MockDockerTransport(httpx.AsyncBaseTransport):
    """Asynchronous HTTPX transport simulating Docker Engine REST v1.43 endpoints."""

    def __init__(self) -> None:
        self.containers: list[dict[str, Any]] = copy.deepcopy(MOCK_CONTAINERS_RAW)
        self._start_time = time.time()
        self._tick = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method.upper()

        # Remove API version prefix if present
        clean_path = path
        if clean_path.startswith("/v1."):
            parts = clean_path.split("/", 2)
            clean_path = "/" + parts[2] if len(parts) > 2 else "/"

        # Ping
        if clean_path == "/_ping":
            return httpx.Response(200, content=b"OK", headers={"content-type": "text/plain"})

        # Version
        if clean_path == "/version":
            payload = {
                "Platform": {"Name": "Docker Engine - Community"},
                "Version": "26.1.1",
                "ApiVersion": "1.45",
                "MinAPIVersion": "1.24",
                "GitCommit": "ac2de78",
                "GoVersion": "go1.21.10",
                "Os": "linux",
                "Arch": "amd64",
                "KernelVersion": "6.6.26-linuxkit",
                "BuildTime": "2026-05-15T10:00:00.000000000+00:00",
            }
            return httpx.Response(200, json=payload)

        # Info
        if clean_path == "/info":
            running = sum(1 for c in self.containers if c.get("State") == "running")
            paused = sum(1 for c in self.containers if c.get("State") == "paused")
            stopped = sum(1 for c in self.containers if c.get("State") in ("exited", "dead"))
            payload = {
                "ID": "dockpulse-simulated-daemon",
                "Containers": len(self.containers),
                "ContainersRunning": running,
                "ContainersPaused": paused,
                "ContainersStopped": stopped,
                "Images": 18,
                "Driver": "overlay2",
                "NCPU": 8,
                "MemTotal": 16 * 1024 * 1024 * 1024,
                "ServerVersion": "26.1.1",
                "OperatingSystem": "Docker Desktop (DockPulse Demo Mode)",
            }
            return httpx.Response(200, json=payload)

        # List containers
        if clean_path == "/containers/json":
            return httpx.Response(200, json=self.containers)

        # Prune containers
        if "prune" in clean_path and method == "POST":
            return httpx.Response(
                200,
                json={
                    "ContainersDeleted": [
                        "30a1b2c3d4e5890123456789abcdef0123456789abcdef0123456789abcdef09"
                    ],
                    "SpaceReclaimed": 52428800,  # 50 MB
                },
            )

        # Container operations
        if clean_path.startswith("/containers/"):
            parts = clean_path.split("/")[2:]
            if not parts:
                return httpx.Response(400, json={"message": "Invalid container path"})

            container_id = parts[0]
            target = next((c for c in self.containers if c["Id"].startswith(container_id)), None)

            # Inspect container
            if len(parts) == 2 and parts[1] == "json" and method == "GET":
                if not target:
                    return httpx.Response(
                        404, json={"message": f"No such container: {container_id}"}
                    )
                inspect_data = {
                    **target,
                    "Config": {
                        "Image": target["Image"],
                        "Cmd": [target.get("Command", "/bin/sh")],
                        "Env": [
                            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                            "NODE_ENV=production",
                            "PORT=8080",
                        ],
                    },
                    "NetworkSettings": {
                        "IPAddress": "172.18.0.4",
                        "Gateway": "172.18.0.1",
                        "Ports": target.get("Ports", []),
                    },
                    "Mounts": [
                        {
                            "Type": "bind",
                            "Source": "/var/run/secrets",
                            "Destination": "/secrets",
                            "Mode": "ro",
                            "RW": False,
                        }
                    ],
                }
                return httpx.Response(200, json=inspect_data)

            # Container lifecycle
            if len(parts) == 2 and method == "POST":
                action = parts[1]
                if not target:
                    return httpx.Response(
                        404, json={"message": f"No such container: {container_id}"}
                    )

                if action == "restart":
                    target["State"] = "running"
                    target["Status"] = "Up less than a second"
                    return httpx.Response(204)
                if action == "stop":
                    target["State"] = "exited"
                    target["Status"] = "Exited (0) just now"
                    return httpx.Response(204)
                if action == "pause":
                    target["State"] = "paused"
                    target["Status"] = "Paused"
                    return httpx.Response(204)
                if action == "unpause":
                    target["State"] = "running"
                    target["Status"] = "Up 4 hours"
                    return httpx.Response(204)

            # Delete container
            if len(parts) == 1 and method == "DELETE":
                if not target:
                    return httpx.Response(
                        404, json={"message": f"No such container: {container_id}"}
                    )
                self.containers = [c for c in self.containers if c["Id"] != target["Id"]]
                return httpx.Response(204)

            # Container stats
            if len(parts) == 2 and parts[1] == "stats" and method == "GET":
                stream_param = request.url.params.get("stream", "true").lower() == "true"
                return self._generate_stats_response(container_id, stream=stream_param)

            # Container logs
            if len(parts) == 2 and parts[1] == "logs" and method == "GET":
                return self._generate_logs_response(target)

            # Exec creation
            if len(parts) == 2 and parts[1] == "exec" and method == "POST":
                return httpx.Response(201, json={"Id": f"exec_mock_{container_id[:8]}"})

        # Exec start
        if clean_path.startswith("/exec/") and clean_path.endswith("/start"):
            output = b"uid=0(root) gid=0(root) groups=0(root)\nLinux 6.6.26-linuxkit #1 SMP PREEMPT_DYNAMIC\n"
            frame = struct.pack(">BxxxI", 1, len(output)) + output
            return httpx.Response(
                200, content=frame, headers={"content-type": "application/vnd.docker.raw-stream"}
            )

        # Images list & removal
        if clean_path == "/images/json" and method == "GET":
            images = [
                {
                    "Id": "sha256:traefik300000000000000000000000000000000000000000000000000000000",
                    "RepoTags": ["traefik:v3.0"],
                    "Size": 44 * 1024 * 1024,
                    "Created": int(time.time()) - 86400 * 14,
                },
                {
                    "Id": "sha256:orderservice21000000000000000000000000000000000000000000000000000",
                    "RepoTags": ["order-service:v2.1.0"],
                    "Size": 218 * 1024 * 1024,
                    "Created": int(time.time()) - 86400 * 2,
                },
                {
                    "Id": "sha256:postgres16alpine00000000000000000000000000000000000000000000000000",
                    "RepoTags": ["postgres:16-alpine"],
                    "Size": 142 * 1024 * 1024,
                    "Created": int(time.time()) - 86400 * 30,
                },
                {
                    "Id": "sha256:redis72alpine0000000000000000000000000000000000000000000000000000",
                    "RepoTags": ["redis:7.2-alpine"],
                    "Size": 38 * 1024 * 1024,
                    "Created": int(time.time()) - 86400 * 45,
                },
                {
                    "Id": "sha256:dangling000000000000000000000000000000000000000000000000000000000",
                    "RepoTags": ["<none>:<none>"],
                    "Size": 184 * 1024 * 1024,
                    "Created": int(time.time()) - 86400 * 5,
                },
            ]
            return httpx.Response(200, json=images)

        if clean_path.startswith("/images/") and method == "DELETE":
            return httpx.Response(200, json=[{"Deleted": clean_path.split("/")[-1]}])

        # Volumes list & removal
        if clean_path == "/volumes" and method == "GET":
            volumes = {
                "Volumes": [
                    {
                        "Name": "order-platform_pgdata",
                        "Driver": "local",
                        "Mountpoint": "/var/lib/docker/volumes/order-platform_pgdata/_data",
                        "UsageData": {"Size": 412 * 1024 * 1024, "RefCount": 1},
                    },
                    {
                        "Name": "order-platform_redisdata",
                        "Driver": "local",
                        "Mountpoint": "/var/lib/docker/volumes/order-platform_redisdata/_data",
                        "UsageData": {"Size": 18 * 1024 * 1024, "RefCount": 1},
                    },
                    {
                        "Name": "orphan_cache_volume_1",
                        "Driver": "local",
                        "Mountpoint": "/var/lib/docker/volumes/orphan_cache_volume_1/_data",
                        "UsageData": {"Size": 850 * 1024 * 1024, "RefCount": 0},
                    },
                ]
            }
            return httpx.Response(200, json=volumes)

        if clean_path.startswith("/volumes/") and method == "DELETE":
            return httpx.Response(204)

        # System disk usage (/system/df)
        if clean_path == "/system/df" and method == "GET":
            df_data = {
                "LayersSize": 2400000000,
                "Images": [
                    {"Size": 44 * 1024 * 1024, "SharedSize": 0},
                    {"Size": 218 * 1024 * 1024, "SharedSize": 0},
                    {"Size": 184 * 1024 * 1024, "SharedSize": 0},
                ],
                "Containers": [{"SizeRw": 1048576} for _ in self.containers],
                "Volumes": [
                    {"UsageData": {"Size": 412 * 1024 * 1024, "RefCount": 1}},
                    {"UsageData": {"Size": 850 * 1024 * 1024, "RefCount": 0}},
                ],
                "BuildCache": [
                    {"Size": 1200 * 1024 * 1024, "Reclaimable": True},
                    {"Size": 800 * 1024 * 1024, "Reclaimable": True},
                ],
            }
            return httpx.Response(200, json=df_data)

        # Prune endpoints
        if "prune" in clean_path and method == "POST":
            return httpx.Response(
                200,
                json={
                    "ContainersDeleted": [
                        "30a1b2c3d4e5890123456789abcdef0123456789abcdef0123456789abcdef09"
                    ],
                    "SpaceReclaimed": 52428800,  # 50 MB
                },
            )

        # Fallback 404
        return httpx.Response(404, json={"message": f"Mock endpoint not found: {method} {path}"})

    def _generate_stats_response(self, container_id: str, stream: bool = True) -> httpx.Response:
        """Generate realistic stats with fluctuating CPU, memory, and network telemetry."""
        now = time.time()
        seed = sum(ord(c) for c in container_id) % 100

        # Sine-based fluctuations for smooth realistic metrics
        cpu_pct_base = 5.0 + (seed % 15)
        cpu_fluctuation = math.sin(now / 2.0 + seed) * 4.0
        calculated_cpu = max(0.5, cpu_pct_base + cpu_fluctuation)

        system_cpu_usage = int(now * 1_000_000_000)
        container_cpu_delta = int((calculated_cpu / 100.0) * 1_000_000_000)
        container_cpu_usage = system_cpu_usage - 100_000_000 + container_cpu_delta

        mem_usage_base = (120 + (seed * 8)) * 1024 * 1024
        mem_fluctuation = int(math.cos(now / 3.0) * 15 * 1024 * 1024)
        mem_usage = max(20 * 1024 * 1024, mem_usage_base + mem_fluctuation)

        stat_payload = {
            "read": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": container_cpu_usage,
                    "percpu_usage": [container_cpu_usage // 4] * 4,
                },
                "system_cpu_usage": system_cpu_usage,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {
                    "total_usage": container_cpu_usage - container_cpu_delta,
                },
                "system_cpu_usage": system_cpu_usage - 1_000_000_000,
                "online_cpus": 4,
            },
            "memory_stats": {
                "usage": mem_usage,
                "limit": 16 * 1024 * 1024 * 1024,
                "stats": {"cache": 24 * 1024 * 1024},
            },
            "networks": {
                "eth0": {
                    "rx_bytes": int(1024 * 1024 * (50 + (now % 60))),
                    "tx_bytes": int(1024 * 1024 * (80 + (now % 60) * 1.5)),
                }
            },
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"major": 8, "minor": 0, "op": "Read", "value": 14200000},
                    {"major": 8, "minor": 0, "op": "Write", "value": 38100000},
                ]
            },
        }

        if not stream:
            return httpx.Response(200, json=stat_payload)

        async def stats_streamer():
            while True:
                line = json.dumps(stat_payload).encode("utf-8") + b"\n"
                yield line
                await asyncio.sleep(1.0)

        return httpx.Response(
            200, content=stats_streamer(), headers={"content-type": "application/json"}
        )

    def _generate_logs_response(self, target: dict[str, Any] | None) -> httpx.Response:
        """Generate 8-byte framed Docker multiplexed logs."""
        service = target.get("Labels", {}).get("com.docker.compose.service", "") if target else ""
        lines = MOCK_LOG_SAMPLES.get(
            service,
            [
                f"[INFO] Container {target.get('Names', ['/unknown'])[0]} initialized successfully",
                "[INFO] Listening for connections on 0.0.0.0",
                "[DEBUG] Healthcheck ping succeeded with code 200",
                "[WARN] Memory threshold warning: memory usage reached 42%",
            ]
            if target
            else ["No logs available"],
        )

        frames = bytearray()
        for idx, text in enumerate(lines):
            stream_id = 2 if "WARN" in text or "error" in text.lower() else 1
            payload = (text + "\n").encode("utf-8")
            header = struct.pack(">BxxxI", stream_id, len(payload))
            frames.extend(header)
            frames.extend(payload)

        return httpx.Response(
            200,
            content=bytes(frames),
            headers={"content-type": "application/vnd.docker.raw-stream"},
        )
