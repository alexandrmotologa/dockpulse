"""Configuration and Docker socket path auto-discovery."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SocketType = Literal["npipe", "unix", "tcp", "mock"]

DEFAULT_WINDOWS_PIPE = r"\\.\pipe\docker_engine"
DEFAULT_UNIX_SOCKET = "/var/run/docker.sock"
DEFAULT_API_VERSION = "v1.43"


@dataclass
class DockerConfig:
    """Docker daemon connection settings."""

    socket_path: str
    socket_type: SocketType
    api_version: str = DEFAULT_API_VERSION
    timeout: float = 10.0
    is_demo: bool = False

    @property
    def base_url(self) -> str:
        """Base URL for HTTP client requests."""
        if self.socket_type == "tcp":
            return self.socket_path.rstrip("/")
        if self.socket_type == "mock":
            return "http://mock-docker"
        return "http://docker"

    @property
    def version_prefix(self) -> str:
        """API version prefix such as /v1.43."""
        if self.api_version:
            ver = self.api_version.lstrip("/")
            return f"/{ver}"
        return ""


def detect_docker_config(
    socket_override: str | None = None,
    demo: bool = False,
    timeout: float = 10.0,
) -> DockerConfig:
    """Detect Docker daemon connection settings from environment or platform defaults."""
    if demo:
        return DockerConfig(
            socket_path="mock://docker_engine",
            socket_type="mock",
            timeout=timeout,
            is_demo=True,
        )

    # 1. Explicit CLI argument override
    if socket_override:
        return _parse_socket_string(socket_override, timeout)

    # 2. Environment variable DOCKER_HOST
    env_host = os.environ.get("DOCKER_HOST", "").strip()
    if env_host:
        return _parse_socket_string(env_host, timeout)

    # 3. Platform defaults
    if sys.platform == "win32":
        return DockerConfig(
            socket_path=DEFAULT_WINDOWS_PIPE,
            socket_type="npipe",
            timeout=timeout,
        )

    # Unix-like: check rootless socket before system socket
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        rootless_path = Path(xdg_runtime) / "docker.sock"
        if rootless_path.exists():
            return DockerConfig(
                socket_path=str(rootless_path),
                socket_type="unix",
                timeout=timeout,
            )

    return DockerConfig(
        socket_path=DEFAULT_UNIX_SOCKET,
        socket_type="unix",
        timeout=timeout,
    )


def _parse_socket_string(target: str, timeout: float) -> DockerConfig:
    """Parse a socket address string into DockerConfig."""
    target_clean = target.strip()

    if target_clean.startswith("mock://") or target_clean == "mock":
        return DockerConfig(
            socket_path="mock://docker_engine",
            socket_type="mock",
            timeout=timeout,
            is_demo=True,
        )

    if (
        target_clean.startswith("npipe://")
        or target_clean.startswith("//./pipe/")
        or target_clean.startswith(r"\\.\pipe\\")
    ):
        clean_path = target_clean.removeprefix("npipe://")
        if clean_path.startswith("//./pipe/"):
            clean_path = r"\\.\pipe\\" + clean_path.removeprefix("//./pipe/")
        return DockerConfig(
            socket_path=clean_path,
            socket_type="npipe",
            timeout=timeout,
        )

    if target_clean.startswith("unix://"):
        return DockerConfig(
            socket_path=target_clean.removeprefix("unix://"),
            socket_type="unix",
            timeout=timeout,
        )

    if (
        target_clean.startswith("tcp://")
        or target_clean.startswith("http://")
        or target_clean.startswith("https://")
    ):
        return DockerConfig(
            socket_path=target_clean,
            socket_type="tcp",
            timeout=timeout,
        )

    # Path check: if it looks like a file path
    if "/" in target_clean or "\\" in target_clean:
        if sys.platform == "win32" and "pipe" in target_clean.lower():
            return DockerConfig(
                socket_path=target_clean,
                socket_type="npipe",
                timeout=timeout,
            )
        return DockerConfig(
            socket_path=target_clean,
            socket_type="unix",
            timeout=timeout,
        )

    return DockerConfig(
        socket_path=target_clean,
        socket_type="tcp",
        timeout=timeout,
    )


@dataclass
class UserPreferences:
    """User configuration loaded from dockpulse.toml or ~/.config/dockpulse/config.toml."""

    theme: str = "default"
    log_tail_lines: int = 100
    show_timestamps: bool = True
    custom_shell: str = "sh"


def load_user_preferences() -> UserPreferences:
    """Load user preferences from local or user-level TOML configuration file."""
    import tomllib

    candidates = [
        Path("dockpulse.toml"),
        Path.home() / ".config" / "dockpulse" / "config.toml",
    ]

    for path in candidates:
        if path.is_file():
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                    ui = data.get("ui", {})
                    shell = data.get("shell", {})
                    return UserPreferences(
                        theme=ui.get("theme", "default"),
                        log_tail_lines=int(ui.get("log_tail_lines", 100)),
                        show_timestamps=bool(ui.get("show_timestamps", True)),
                        custom_shell=str(shell.get("command", "sh")),
                    )
            except Exception:
                continue

    return UserPreferences()
