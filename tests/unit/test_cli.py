"""Tests for CLI subcommands."""

from typer.testing import CliRunner

from dockpulse.cli import app

runner = CliRunner(env={"COLUMNS": "160"})


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "dockpulse v0.1.0" in result.stdout


def test_cli_ps_demo() -> None:
    result = runner.invoke(app, ["ps", "--demo"])
    assert result.exit_code == 0
    assert "DockPulse Containers" in result.stdout
    assert "order-platform" in result.stdout
    assert "api-gateway" in result.stdout


def test_cli_stats_demo() -> None:
    result = runner.invoke(app, ["stats", "--demo"])
    assert result.exit_code == 0
    assert "Container Resource Snapshot" in result.stdout
    assert "CPU" in result.stdout
    assert "Memory" in result.stdout


def test_cli_logs_demo() -> None:
    result = runner.invoke(app, ["logs", "api-gateway", "--demo"])
    assert result.exit_code == 0
    assert "Tailing logs for order-platform-api-gateway-1" in result.stdout


def test_cli_prune_demo() -> None:
    result = runner.invoke(app, ["prune", "--force", "--demo"])
    assert result.exit_code == 0
    assert "Prune complete!" in result.stdout


def test_cli_check() -> None:
    # Will check current environment (expected to report connection fail or ok)
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "Docker Engine Diagnostics" in result.stdout
