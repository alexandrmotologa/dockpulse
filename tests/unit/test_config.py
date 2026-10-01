"""Tests for DockerConfig and socket auto-discovery."""

import os
from unittest.mock import patch

from dockpulse.config import DockerConfig, detect_docker_config, save_user_theme


def test_detect_docker_config_demo() -> None:
    config = detect_docker_config(demo=True)
    assert config.is_demo is True
    assert config.socket_type == "mock"
    assert config.base_url == "http://mock-docker"


def test_detect_docker_config_explicit_unix() -> None:
    config = detect_docker_config(socket_override="unix:///custom/path/docker.sock")
    assert config.socket_type == "unix"
    assert config.socket_path == "/custom/path/docker.sock"


def test_detect_docker_config_explicit_npipe() -> None:
    config = detect_docker_config(socket_override="npipe:////./pipe/custom_pipe")
    assert config.socket_type == "npipe"
    assert "custom_pipe" in config.socket_path


def test_detect_docker_config_explicit_tcp() -> None:
    config = detect_docker_config(socket_override="tcp://127.0.0.1:2375")
    assert config.socket_type == "tcp"
    assert config.socket_path == "tcp://127.0.0.1:2375"


def test_detect_docker_config_env_variable() -> None:
    with patch.dict(os.environ, {"DOCKER_HOST": "unix:///env/docker.sock"}):
        config = detect_docker_config()
        assert config.socket_type == "unix"
        assert config.socket_path == "/env/docker.sock"


def test_version_prefix() -> None:
    cfg = DockerConfig(socket_path="/var/run/docker.sock", socket_type="unix", api_version="v1.43")
    assert cfg.version_prefix == "/v1.43"

    cfg_no_v = DockerConfig(socket_path="/var/run/docker.sock", socket_type="unix", api_version="")
    assert cfg_no_v.version_prefix == ""


def test_save_user_theme(tmp_path: os.PathLike) -> None:
    with patch("dockpulse.config.Path") as mock_path:
        test_file = mock_path.return_value
        test_file.is_file.return_value = True
        test_file.exists.return_value = True
        test_file.read_text.return_value = '[ui]\ntheme = "default"\n'

        success = save_user_theme("tokyo_night")
        assert success is True
        test_file.write_text.assert_called_once()
        written = test_file.write_text.call_args[0][0]
        assert 'theme = "tokyo_night"' in written
