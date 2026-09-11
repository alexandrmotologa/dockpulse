"""Unit and integration tests for new features (Compose stacks, images, volumes, logs, themes)."""

from pathlib import Path

import pytest

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.config import DockerConfig, load_user_preferences
from dockpulse.core.clipboard import copy_to_clipboard
from dockpulse.core.container import ContainerModel
from dockpulse.core.log_multiplexer import LogLine, LogMultiplexer
from dockpulse.core.theme import get_theme


def test_container_model_web_url_and_connection() -> None:
    # Web port 8080
    c_web = ContainerModel.model_validate(
        {
            "Id": "abc1234567890",
            "Names": ["/web-gateway"],
            "Image": "traefik:v3.0",
            "State": "running",
            "Ports": [{"PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}],
        }
    )
    assert c_web.web_url == "http://localhost:8080"
    assert "8080" in c_web.connection_info

    # Postgres connection string
    c_pg = ContainerModel.model_validate(
        {
            "Id": "pg1234567890",
            "Names": ["/postgres-database"],
            "Image": "postgres:16-alpine",
            "State": "running",
            "Ports": [{"PrivatePort": 5432, "PublicPort": 5432, "Type": "tcp"}],
        }
    )
    assert "postgresql://" in c_pg.connection_info
    assert ":5432" in c_pg.connection_info

    # Redis connection string
    c_redis = ContainerModel.model_validate(
        {
            "Id": "redis1234567890",
            "Names": ["/redis-cache"],
            "Image": "redis:7.2",
            "State": "running",
            "Ports": [{"PrivatePort": 6379, "PublicPort": 6379, "Type": "tcp"}],
        }
    )
    assert c_redis.connection_info == "redis://localhost:6379"


def test_watchdog_anomaly_detection() -> None:
    # OOMKilled container
    c_oom = ContainerModel.model_validate(
        {
            "Id": "oom1234567890",
            "Names": ["/crashed-worker"],
            "Image": "python:3.12",
            "State": "exited",
            "Status": "Exited (137) 2 minutes ago",
        }
    )
    assert c_oom.is_oom_killed is True
    assert "oom_killed" in c_oom.status_badge

    # Crash loop container
    c_crash = ContainerModel.model_validate(
        {
            "Id": "crash1234567890",
            "Names": ["/flapping-api"],
            "Image": "node:20",
            "State": "restarting",
            "Status": "Restarting (1) 5 seconds ago",
        }
    )
    assert c_crash.is_crash_loop is True
    assert "crash_loop" in c_crash.status_badge


def test_log_line_timestamps_and_severity() -> None:
    line_err = LogLine(stream_id=2, text="[2026-09-11 14:15:02] FATAL: connection refused")
    assert line_err.timestamp == "2026-09-11 14:15:02"
    assert line_err.severity == "ERROR"
    assert "FATAL" in line_err.clean_text

    line_iso = LogLine(stream_id=1, text="2026-09-11T14:15:02Z INFO: Order processed")
    assert line_iso.timestamp == "2026-09-11T14:15:02Z"
    assert line_iso.severity == "INFO"

    markup_with_ts = line_err.render_markup(show_timestamp=True)
    assert "2026-09-11" in markup_with_ts
    assert "ERR" in markup_with_ts

    markup_without_ts = line_err.render_markup(show_timestamp=False)
    assert "2026-09-11" not in markup_without_ts


def test_log_multiplexer_severity_filter_and_export(tmp_path: Path) -> None:
    mux = LogMultiplexer()
    mux.add_line(1, "INFO: service starting")
    mux.add_line(1, "WARN: slow database query took 450ms")
    mux.add_line(2, "ERROR: transaction failed")

    # All
    assert len(mux.get_lines()) == 3

    # Warn+
    warn_lines = mux.get_lines(min_severity="WARN")
    assert len(warn_lines) == 2

    # Error only
    err_lines = mux.get_lines(min_severity="ERROR")
    assert len(err_lines) == 1
    assert "ERROR: transaction failed" in err_lines[0].text

    # File export
    log_file = tmp_path / "test_export.log"
    written_count = mux.export_to_file(log_file)
    assert written_count == 3
    assert log_file.exists()
    assert "transaction failed" in log_file.read_text(encoding="utf-8")


def test_theme_engine() -> None:
    for theme_name in ("default", "tokyo_night", "catppuccin", "dracula", "nord"):
        palette = get_theme(theme_name)
        assert palette.name == theme_name
        css = palette.generate_css()
        assert "HeaderBar" in css
        assert palette.accent in css

    fallback = get_theme("non_existent_theme")
    assert fallback.name == "default"


def test_load_user_preferences() -> None:
    prefs = load_user_preferences()
    assert prefs.theme == "default"
    assert prefs.show_timestamps is True


def test_clipboard_utility() -> None:
    # Test that calling copy_to_clipboard with valid text returns a boolean without throwing an unhandled exception
    res = copy_to_clipboard("test copy")
    assert isinstance(res, bool)


@pytest.mark.asyncio
async def test_api_client_compose_stacks_and_storage() -> None:
    config = DockerConfig(socket_path="mock://docker_engine", socket_type="mock", is_demo=True)
    client = DockerApiClient(config=config)

    async with client:
        # Stack restart & stop
        restarted = await client.restart_compose_project("order-platform")
        assert restarted >= 3

        stopped = await client.stop_compose_project("order-platform")
        assert stopped >= 3

        # Images
        images = await client.list_images()
        assert len(images) >= 4
        removed_img = await client.remove_image(images[0]["Id"])
        assert removed_img is True

        # Volumes
        volumes = await client.list_volumes()
        assert len(volumes) >= 2
        removed_vol = await client.remove_volume("orphan_cache_volume_1")
        assert removed_vol is True

        # Disk usage (system df)
        df_data = await client.get_disk_usage()
        assert "Images" in df_data
        assert "Volumes" in df_data
        assert "BuildCache" in df_data
