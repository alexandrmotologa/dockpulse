"""Real-time Docker resource telemetry calculation (CPU %, Memory RSS, Network I/O, Block I/O)."""

import time
from dataclasses import dataclass
from typing import Any


def format_bytes(num_bytes: float | int) -> str:
    """Format bytes into human-readable KiB/MiB/GiB."""
    b = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0 or unit == "TB":
            return f"{b:.1f} {unit}" if unit != "B" else f"{int(b)} B"
        b /= 1024.0
    return f"{b:.1f} TB"


@dataclass
class ContainerStatsSnapshot:
    """Calculated point-in-time container resource telemetry."""

    timestamp: float
    cpu_percent: float
    memory_bytes: int
    memory_limit: int
    memory_percent: float
    net_rx_bytes: int
    net_tx_bytes: int
    net_rx_rate: float  # bytes per second
    net_tx_rate: float  # bytes per second
    block_read_bytes: int
    block_write_bytes: int

    @property
    def cpu_display(self) -> str:
        return f"{self.cpu_percent:5.1f}%"

    @property
    def memory_display(self) -> str:
        used = format_bytes(self.memory_bytes)
        limit = format_bytes(self.memory_limit)
        return f"{used} / {limit} ({self.memory_percent:.1f}%)"

    @property
    def network_display(self) -> str:
        rx = format_bytes(self.net_rx_rate)
        tx = format_bytes(self.net_tx_rate)
        return f"▼ {rx}/s  ▲ {tx}/s"

    @property
    def block_io_display(self) -> str:
        r = format_bytes(self.block_read_bytes)
        w = format_bytes(self.block_write_bytes)
        return f"R: {r}  W: {w}"


class ContainerStatsCalculator:
    """Computes CPU delta percentage, memory RSS, and network rates across updates."""

    def __init__(self) -> None:
        self._prev_cpu: int | None = None
        self._prev_system: int | None = None
        self._prev_time: float = time.time()
        self._prev_net_rx: int | None = None
        self._prev_net_tx: int | None = None

    def calculate(self, raw: dict[str, Any]) -> ContainerStatsSnapshot:
        """Parse raw Docker stats JSON and compute resource usage."""
        now = time.time()
        time_delta = max(0.001, now - self._prev_time)

        # 1. CPU Usage Calculation
        cpu_stats = raw.get("cpu_stats", {})
        precpu_stats = raw.get("precpu_stats", {})

        container_cpu = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        system_cpu = cpu_stats.get("system_cpu_usage", 0)

        prev_container_cpu = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        prev_system_cpu = precpu_stats.get("system_cpu_usage", 0)

        # Fallback to internal tracker if precpu_stats is empty
        if prev_container_cpu == 0 and self._prev_cpu is not None:
            prev_container_cpu = self._prev_cpu
        if prev_system_cpu == 0 and self._prev_system is not None:
            prev_system_cpu = self._prev_system

        cpu_delta = container_cpu - prev_container_cpu
        system_delta = system_cpu - prev_system_cpu
        online_cpus = cpu_stats.get("online_cpus") or len(
            cpu_stats.get("cpu_usage", {}).get("percpu_usage", []) or [1]
        )
        online_cpus = max(1, online_cpus)

        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta >= 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0

        self._prev_cpu = container_cpu
        self._prev_system = system_cpu

        # 2. Memory Usage Calculation
        mem_stats = raw.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0)
        mem_limit = mem_stats.get("limit", 1)

        # Deduct cache/inactive_file to reflect true RSS memory
        stats_sub = mem_stats.get("stats", {})
        cache = stats_sub.get("cache") or stats_sub.get("inactive_file", 0)
        clean_usage = max(0, mem_usage - cache) if cache < mem_usage else mem_usage

        mem_percent = (clean_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0

        # 3. Network I/O
        networks = raw.get("networks", {})
        total_rx = sum(net.get("rx_bytes", 0) for net in networks.values())
        total_tx = sum(net.get("tx_bytes", 0) for net in networks.values())

        rx_rate = 0.0
        tx_rate = 0.0
        if self._prev_net_rx is not None and total_rx >= self._prev_net_rx:
            rx_rate = (total_rx - self._prev_net_rx) / time_delta
        if self._prev_net_tx is not None and total_tx >= self._prev_net_tx:
            tx_rate = (total_tx - self._prev_net_tx) / time_delta

        self._prev_net_rx = total_rx
        self._prev_net_tx = total_tx
        self._prev_time = now

        # 4. Block I/O
        blkio = raw.get("blkio_stats", {})
        io_entries = blkio.get("io_service_bytes_recursive", []) or []
        block_read = sum(
            entry.get("value", 0) for entry in io_entries if entry.get("op", "").lower() == "read"
        )
        block_write = sum(
            entry.get("value", 0) for entry in io_entries if entry.get("op", "").lower() == "write"
        )

        return ContainerStatsSnapshot(
            timestamp=now,
            cpu_percent=round(cpu_percent, 2),
            memory_bytes=clean_usage,
            memory_limit=mem_limit,
            memory_percent=round(mem_percent, 2),
            net_rx_bytes=total_rx,
            net_tx_bytes=total_tx,
            net_rx_rate=round(rx_rate, 1),
            net_tx_rate=round(tx_rate, 1),
            block_read_bytes=block_read,
            block_write_bytes=block_write,
        )
