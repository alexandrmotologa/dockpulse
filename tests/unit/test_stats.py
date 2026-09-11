"""Tests for ContainerStatsCalculator and SparklineBuffer."""

from dockpulse.core.sparkline_buffer import SparklineBuffer
from dockpulse.core.stats_streamer import ContainerStatsCalculator, format_bytes


def test_format_bytes() -> None:
    assert format_bytes(512) == "512 B"
    assert "KB" in format_bytes(2048)
    assert "MB" in format_bytes(50 * 1024 * 1024)
    assert "GB" in format_bytes(4 * 1024 * 1024 * 1024)


def test_stats_calculator_cpu_and_memory() -> None:
    calc = ContainerStatsCalculator()

    raw_sample = {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 200_000_000},
            "system_cpu_usage": 1_000_000_000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100_000_000},
            "system_cpu_usage": 500_000_000,
            "online_cpus": 2,
        },
        "memory_stats": {
            "usage": 256 * 1024 * 1024,
            "limit": 1024 * 1024 * 1024,
            "stats": {"cache": 56 * 1024 * 1024},
        },
        "networks": {
            "eth0": {"rx_bytes": 10240, "tx_bytes": 20480},
        },
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"op": "Read", "value": 1000},
                {"op": "Write", "value": 2000},
            ]
        },
    }

    snapshot = calc.calculate(raw_sample)

    # CPU: (100M / 500M) * 2 * 100 = 40.0%
    assert snapshot.cpu_percent == 40.0
    # Memory: 256MB - 56MB cache = 200MB
    assert snapshot.memory_bytes == 200 * 1024 * 1024
    assert snapshot.memory_percent == round((200 / 1024) * 100.0, 2)
    assert snapshot.block_read_bytes == 1000
    assert snapshot.block_write_bytes == 2000
    assert "%" in snapshot.cpu_display
    assert "/" in snapshot.memory_display


def test_sparkline_buffer_rendering() -> None:
    buf = SparklineBuffer(capacity=10)
    assert buf.render(width=5) == "     "

    buf.push(0.0)
    buf.push(50.0)
    buf.push(100.0)

    rendered = buf.render(width=3, max_scale=100.0)
    assert len(rendered) == 3
    # First should be low, last should be high
    assert rendered[0] == " "
    assert rendered[-1] == "█"
    assert buf.latest == 100.0
    assert buf.min_val == 0.0
    assert buf.max_val == 100.0
