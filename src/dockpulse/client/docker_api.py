"""Asynchronous client for the Docker Engine REST API v1.43."""

import asyncio
import json
import struct
from collections.abc import AsyncIterator
from typing import Any

import httpx

from dockpulse.client.socket_transport import create_docker_client
from dockpulse.config import DockerConfig, detect_docker_config
from dockpulse.core.container import ContainerModel


class DockerApiError(Exception):
    """Raised when the Docker Engine returns an error status code or unexpected payload."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DockerApiClient:
    """High-performance asynchronous client for Docker Engine REST v1.43."""

    def __init__(
        self,
        config: DockerConfig | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or detect_docker_config()
        self._external_client = client is not None
        self._client = client or create_docker_client(self.config)

    async def __aenter__(self) -> "DockerApiClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client transport if owned."""
        if not self._external_client and not self._client.is_closed:
            await self._client.aclose()

    def _url(self, path: str) -> str:
        """Format an endpoint path with the configured API version prefix."""
        prefix = self.config.version_prefix
        clean_path = "/" + path.lstrip("/")
        return f"{prefix}{clean_path}"

    async def ping(self) -> bool:
        """Check if the Docker daemon responds to ping."""
        try:
            resp = await self._client.get("/_ping", timeout=3.0)
            return resp.status_code == 200 and b"OK" in resp.content
        except Exception:
            return False

    async def get_version(self) -> dict[str, Any]:
        """Retrieve Docker engine version and host metadata."""
        resp = await self._client.get(self._url("/version"))
        if resp.status_code != 200:
            raise DockerApiError(f"Failed to get version: {resp.text}", resp.status_code)
        return resp.json()

    async def get_system_info(self) -> dict[str, Any]:
        """Retrieve system-wide Docker engine telemetry."""
        resp = await self._client.get(self._url("/info"))
        if resp.status_code != 200:
            raise DockerApiError(f"Failed to get system info: {resp.text}", resp.status_code)
        return resp.json()

    async def list_containers(self, all_containers: bool = True) -> list[ContainerModel]:
        """List active and stopped containers."""
        params = {"all": "1" if all_containers else "0"}
        resp = await self._client.get(self._url("/containers/json"), params=params)
        if resp.status_code != 200:
            raise DockerApiError(f"Failed to list containers: {resp.text}", resp.status_code)

        raw_list = resp.json()
        return [ContainerModel.model_validate(item) for item in raw_list]

    async def inspect_container(self, container_id: str) -> dict[str, Any]:
        """Inspect low-level container details."""
        resp = await self._client.get(self._url(f"/containers/{container_id}/json"))
        if resp.status_code != 200:
            raise DockerApiError(
                f"Failed to inspect container {container_id}: {resp.text}", resp.status_code
            )
        return resp.json()

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restart a running container."""
        resp = await self._client.post(
            self._url(f"/containers/{container_id}/restart"),
            params={"t": str(timeout)},
        )
        return resp.status_code in (204, 200)

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a running container gracefully."""
        resp = await self._client.post(
            self._url(f"/containers/{container_id}/stop"),
            params={"t": str(timeout)},
        )
        return resp.status_code in (204, 200)

    async def pause_container(self, container_id: str) -> bool:
        """Pause execution of a running container."""
        resp = await self._client.post(self._url(f"/containers/{container_id}/pause"))
        return resp.status_code in (204, 200)

    async def unpause_container(self, container_id: str) -> bool:
        """Unpause execution of a paused container."""
        resp = await self._client.post(self._url(f"/containers/{container_id}/unpause"))
        return resp.status_code in (204, 200)

    async def remove_container(
        self, container_id: str, force: bool = False, volumes: bool = False
    ) -> bool:
        """Remove a stopped container."""
        params = {"v": "1" if volumes else "0", "force": "1" if force else "0"}
        resp = await self._client.delete(self._url(f"/containers/{container_id}"), params=params)
        return resp.status_code in (204, 200)

    async def prune_containers(self) -> dict[str, Any]:
        """Delete all stopped containers and report reclaimed disk space."""
        resp = await self._client.post(self._url("/containers/prune"))
        if resp.status_code != 200:
            raise DockerApiError(f"Prune failed: {resp.text}", resp.status_code)
        return resp.json()

    async def restart_compose_project(self, project_name: str) -> int:
        """Restart all containers belonging to a Docker Compose project concurrently.

        Returns:
            Number of restarted containers.
        """
        all_conts = await self.list_containers(all_containers=True)
        targets = [c for c in all_conts if c.compose_project == project_name]
        if not targets:
            return 0
        tasks = [self.restart_container(c.id) for c in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)

    async def stop_compose_project(self, project_name: str) -> int:
        """Stop all running containers in a Docker Compose project concurrently.

        Returns:
            Number of stopped containers.
        """
        all_conts = await self.list_containers(all_containers=True)
        targets = [c for c in all_conts if c.compose_project == project_name and c.is_running]
        if not targets:
            return 0
        tasks = [self.stop_container(c.id) for c in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)

    async def list_images(self) -> list[dict[str, Any]]:
        """List local Docker images with size and repo tags."""
        resp = await self._client.get(self._url("/images/json"))
        if resp.status_code != 200:
            raise DockerApiError(f"Failed to list images: {resp.text}", resp.status_code)
        return resp.json()

    async def remove_image(self, image_id: str, force: bool = False) -> bool:
        """Remove a local Docker image."""
        params = {"force": "1" if force else "0"}
        resp = await self._client.delete(self._url(f"/images/{image_id}"), params=params)
        return resp.status_code in (200, 204)

    async def list_volumes(self) -> list[dict[str, Any]]:
        """List local Docker volumes."""
        resp = await self._client.get(self._url("/volumes"))
        if resp.status_code != 200:
            raise DockerApiError(f"Failed to list volumes: {resp.text}", resp.status_code)
        data = resp.json()
        return data.get("Volumes", []) or []

    async def remove_volume(self, volume_name: str, force: bool = False) -> bool:
        """Remove a local Docker volume."""
        params = {"force": "1" if force else "0"}
        resp = await self._client.delete(self._url(f"/volumes/{volume_name}"), params=params)
        return resp.status_code in (200, 204)

    async def get_disk_usage(self) -> dict[str, Any]:
        """Get Docker engine data usage statistics (images, containers, volumes, build cache)."""
        resp = await self._client.get(self._url("/system/df"))
        if resp.status_code != 200:
            raise DockerApiError(f"Failed to get disk usage: {resp.text}", resp.status_code)
        return resp.json()

    async def stream_stats(self, container_id: str) -> AsyncIterator[dict[str, Any]]:
        """Stream real-time resource statistics for a container."""
        url = self._url(f"/containers/{container_id}/stats")
        params = {"stream": "true"}

        async with self._client.stream("GET", url, params=params, timeout=None) as response:
            if response.status_code != 200:
                raise DockerApiError(
                    f"Stats stream failed: {response.status_code}", response.status_code
                )

            async for line in response.aiter_lines():
                line_str = line.strip()
                if line_str:
                    try:
                        yield json.loads(line_str)
                    except json.JSONDecodeError:
                        continue

    async def stream_logs(
        self,
        container_id: str,
        tail: int = 100,
        follow: bool = True,
        stdout: bool = True,
        stderr: bool = True,
        timestamps: bool = False,
    ) -> AsyncIterator[tuple[int, str]]:
        """Stream demultiplexed container logs.

        Yields:
            (stream_type, line_text) where stream_type is 1 for stdout, 2 for stderr.
        """
        url = self._url(f"/containers/{container_id}/logs")
        params = {
            "tail": str(tail),
            "follow": "1" if follow else "0",
            "stdout": "1" if stdout else "0",
            "stderr": "1" if stderr else "0",
            "timestamps": "1" if timestamps else "0",
        }

        async with self._client.stream("GET", url, params=params, timeout=None) as response:
            if response.status_code != 200:
                raise DockerApiError(
                    f"Logs stream failed: {response.status_code}", response.status_code
                )

            buffer = bytearray()
            async for chunk in response.aiter_bytes():
                buffer.extend(chunk)
                while len(buffer) >= 8:
                    stream_id, size = struct.unpack(">BxxxI", buffer[:8])
                    total_frame = 8 + size
                    if len(buffer) < total_frame:
                        break

                    payload = buffer[8:total_frame]
                    buffer = buffer[total_frame:]

                    text = payload.decode("utf-8", errors="replace").rstrip("\r\n")
                    if text:
                        yield (stream_id, text)

    async def create_exec(
        self, container_id: str, cmd: list[str], tty: bool = True, stdin: bool = True
    ) -> str:
        """Create an exec instance for running interactive commands inside a container."""
        payload = {
            "AttachStdin": stdin,
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": tty,
            "Cmd": cmd,
        }
        resp = await self._client.post(self._url(f"/containers/{container_id}/exec"), json=payload)
        if resp.status_code not in (201, 200):
            raise DockerApiError(f"Failed to create exec: {resp.text}", resp.status_code)
        return resp.json()["Id"]

    async def start_exec(self, exec_id: str, tty: bool = True) -> AsyncIterator[bytes]:
        """Start an exec instance and stream output."""
        payload = {"Detach": False, "Tty": tty}
        async with self._client.stream(
            "POST",
            self._url(f"/exec/{exec_id}/start"),
            json=payload,
            timeout=None,
        ) as response:
            if response.status_code != 200:
                raise DockerApiError(
                    f"Failed to start exec: {response.status_code}", response.status_code
                )
            async for chunk in response.aiter_bytes():
                yield chunk
