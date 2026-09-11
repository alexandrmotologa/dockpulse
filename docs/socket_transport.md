# Socket Transport

DockPulse communicates with Docker Engine using raw operating system sockets rather than wrapping the `docker` CLI binary.

## Supported Socket Types

1. **Windows Named Pipe** (`\\.\pipe\docker_engine`)
   - Default on Windows when Docker Desktop or dockerd runs in Windows container mode.
   - Handled via asynchronous pipe streams in Python.
2. **Unix Domain Socket** (`/var/run/docker.sock`)
   - Standard path on Linux and macOS.
   - Rootless Docker path: `$XDG_RUNTIME_DIR/docker.sock` (typically `/run/user/<uid>/docker.sock`).
   - Integrated with `httpx` async UDS transport.
3. **TCP Socket** (`tcp://host:port` or `http://host:port`)
   - Used when Docker exposes a remote TCP port (default 2375 or 2376 with TLS).
4. **Mock Transport** (`mock://`)
   - In-memory simulated engine for `--demo` mode and offline test execution.

## Multiplexed Stream Protocol

Docker multiplexes `stdout` and `stderr` streams across a single connection using an 8-byte framing header on each packet:

```
+-----------+--------------+--------------+
| Stream ID | Reserved (3) |  Frame Size  |
|  (1 byte) |   (3 bytes)  |   (4 bytes)  |
+-----------+--------------+--------------+
```

- `0x00`: Standard input (stdin)
- `0x01`: Standard output (stdout)
- `0x02`: Standard error (stderr)
- Frame size: 32-bit big-endian unsigned integer representing payload byte length.

`LogMultiplexer` decodes this header, buffers incomplete chunks, and emits structured log lines with source markers.
