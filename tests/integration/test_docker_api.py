"""Integration tests for DockerApiClient using MockDockerTransport."""

import pytest

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.config import DockerConfig


@pytest.fixture
def mock_api_client() -> DockerApiClient:
    config = DockerConfig(socket_path="mock://docker_engine", socket_type="mock", is_demo=True)
    return DockerApiClient(config=config)


@pytest.mark.asyncio
async def test_ping(mock_api_client: DockerApiClient) -> None:
    async with mock_api_client:
        result = await mock_api_client.ping()
        assert result is True


@pytest.mark.asyncio
async def test_get_version(mock_api_client: DockerApiClient) -> None:
    async with mock_api_client:
        version_data = await mock_api_client.get_version()
        assert "Version" in version_data
        assert version_data["Version"] == "26.1.1"


@pytest.mark.asyncio
async def test_get_system_info(mock_api_client: DockerApiClient) -> None:
    async with mock_api_client:
        info = await mock_api_client.get_system_info()
        assert info["Containers"] > 0
        assert info["ContainersRunning"] > 0


@pytest.mark.asyncio
async def test_list_containers(mock_api_client: DockerApiClient) -> None:
    async with mock_api_client:
        containers = await mock_api_client.list_containers(all_containers=True)
        assert len(containers) >= 5
        order_api = next(
            (c for c in containers if "order-platform-api-gateway" in c.primary_name), None
        )
        assert order_api is not None
        assert order_api.compose_project == "order-platform"


@pytest.mark.asyncio
async def test_container_lifecycle(mock_api_client: DockerApiClient) -> None:
    async with mock_api_client:
        containers = await mock_api_client.list_containers()
        target_id = containers[0].id

        # Restart
        restarted = await mock_api_client.restart_container(target_id)
        assert restarted is True

        # Stop
        stopped = await mock_api_client.stop_container(target_id)
        assert stopped is True

        # Pause
        paused = await mock_api_client.pause_container(target_id)
        assert paused is True

        # Unpause
        unpaused = await mock_api_client.unpause_container(target_id)
        assert unpaused is True


@pytest.mark.asyncio
async def test_stream_logs(mock_api_client: DockerApiClient) -> None:
    async with mock_api_client:
        containers = await mock_api_client.list_containers()
        target_id = containers[0].id

        collected_lines = []
        async for stream_id, line in mock_api_client.stream_logs(target_id, tail=10, follow=False):
            collected_lines.append((stream_id, line))
            if len(collected_lines) >= 3:
                break

        assert len(collected_lines) > 0
        assert collected_lines[0][0] in (1, 2)  # stdout or stderr
