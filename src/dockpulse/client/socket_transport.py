"""Socket transport implementations for Docker Engine (Windows Named Pipe, Unix Socket, TCP)."""

import asyncio
import sys
import typing
from collections.abc import AsyncIterable

import httpcore
import httpx
from httpx._transports.default import AsyncResponseStream, map_httpcore_exceptions

from dockpulse.config import DockerConfig


class NamedPipeNetworkStream(httpcore.AsyncNetworkStream):
    """Network stream adapter wrapping an asyncio StreamReader/StreamWriter connected to a Named Pipe."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        if timeout is not None:
            return await asyncio.wait_for(self._reader.read(max_bytes), timeout)
        return await self._reader.read(max_bytes)

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._writer.write(buffer)
        if timeout is not None:
            await asyncio.wait_for(self._writer.drain(), timeout)
        else:
            await self._writer.drain()

    async def aclose(self) -> None:
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass

    async def start_tls(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> httpcore.AsyncNetworkStream:
        raise NotImplementedError("TLS is not supported on Windows Named Pipes")

    def get_extra_info(self, info: str) -> typing.Any:
        return None


class NamedPipeNetworkBackend(httpcore.AsyncNetworkBackend):
    """Network backend connecting to a Windows Named Pipe address."""

    def __init__(self, pipe_path: str) -> None:
        self._pipe_path = pipe_path

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Any = None,
    ) -> httpcore.AsyncNetworkStream:
        loop = asyncio.get_running_loop()

        if not hasattr(loop, "create_pipe_connection"):
            raise RuntimeError(
                f"Current event loop {loop!r} does not support named pipes (ProactorEventLoop required on Windows)"
            )

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        connect_coro = loop.create_pipe_connection(lambda: protocol, self._pipe_path)

        if timeout is not None:
            transport, _ = await asyncio.wait_for(connect_coro, timeout)
        else:
            transport, _ = await connect_coro

        writer = asyncio.StreamWriter(transport, protocol, reader, loop)
        return NamedPipeNetworkStream(reader, writer)

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: typing.Any = None
    ) -> httpcore.AsyncNetworkStream:
        raise NotImplementedError("Use connect_tcp for Windows Named Pipes")

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class WindowsNamedPipeTransport(httpx.AsyncBaseTransport):
    """HTTPX transport for Windows Named Pipe connections."""

    def __init__(self, pipe_path: str) -> None:
        self.pipe_path = pipe_path
        backend = NamedPipeNetworkBackend(pipe_path)
        self._pool = httpcore.AsyncConnectionPool(network_backend=backend, retries=0)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with map_httpcore_exceptions():
            resp = await self._pool.handle_async_request(req)

        assert isinstance(resp.stream, AsyncIterable)

        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=AsyncResponseStream(resp.stream),
            extensions=resp.extensions,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()


def create_docker_client(config: DockerConfig) -> httpx.AsyncClient:
    """Create an HTTPX async client configured for the target Docker socket."""
    if config.socket_type == "mock":
        from dockpulse.client.mock_transport import MockDockerTransport

        return httpx.AsyncClient(
            transport=MockDockerTransport(),
            base_url=config.base_url,
            timeout=config.timeout,
        )

    if config.socket_type == "unix":
        transport = httpx.AsyncHTTPTransport(uds=config.socket_path)
        return httpx.AsyncClient(
            transport=transport,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    if config.socket_type == "npipe":
        if sys.platform != "win32":
            raise RuntimeError("Windows Named Pipe transport is only supported on Windows")
        transport = WindowsNamedPipeTransport(config.socket_path)
        return httpx.AsyncClient(
            transport=transport,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    # TCP / HTTP
    return httpx.AsyncClient(
        base_url=config.base_url,
        timeout=config.timeout,
    )
