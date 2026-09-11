"""Multiplexed Docker log parsing, stdout/stderr framing, and search filtering."""

import re
import struct
from collections import deque
from dataclasses import dataclass


@dataclass
class LogLine:
    """Single demultiplexed log entry with source stream identity."""

    stream_id: int  # 1: stdout, 2: stderr
    text: str

    @property
    def is_stderr(self) -> bool:
        return self.stream_id == 2

    @property
    def stream_name(self) -> str:
        return "STDERR" if self.is_stderr else "STDOUT"

    def render_markup(self) -> str:
        """Render formatted line with Rich console markup tags."""
        escaped = self.text.replace("[", "\\[").replace("]", "\\]")
        if self.is_stderr:
            return f"[bold red]ERR[/] [red]{escaped}[/]"
        return f"[dim cyan]OUT[/] {escaped}"


class LogMultiplexer:
    """Manages container log history, framing demultiplexing, and search filtering."""

    def __init__(self, max_lines: int = 1000) -> None:
        self.max_lines = max_lines
        self._lines: deque[LogLine] = deque(maxlen=self.max_lines)

    def add_line(self, stream_id: int, text: str) -> LogLine:
        """Add a log line to the rolling buffer."""
        line = LogLine(stream_id=stream_id, text=text)
        self._lines.append(line)
        return line

    def clear(self) -> None:
        """Empty the stored log buffer."""
        self._lines.clear()

    @property
    def count(self) -> int:
        return len(self._lines)

    def get_lines(self, query: str | None = None) -> list[LogLine]:
        """Return lines, optionally filtered by a case-insensitive regex or substring search."""
        if not query:
            return list(self._lines)

        try:
            pattern = re.compile(query, re.IGNORECASE)
            return [line for line in self._lines if pattern.search(line.text)]
        except re.error:
            # Fallback to plain substring search if regex syntax is invalid
            q_lower = query.lower()
            return [line for line in self._lines if q_lower in line.text.lower()]

    def export_text(self) -> str:
        """Export raw unformatted logs as a single string."""
        return "\n".join(f"[{line.stream_name}] {line.text}" for line in self._lines)

    @staticmethod
    def parse_docker_frames(buffer: bytearray) -> list[tuple[int, str]]:
        """Parse Docker 8-byte framed byte buffers into (stream_id, text) tuples.

        Docker multiplexing header layout:
        - byte 0: stream type (0=stdin, 1=stdout, 2=stderr)
        - bytes 1-3: padding (0x00, 0x00, 0x00)
        - bytes 4-7: 32-bit big-endian payload size
        """
        results: list[tuple[int, str]] = []

        while len(buffer) >= 8:
            stream_id, size = struct.unpack(">BxxxI", buffer[:8])
            total_frame_len = 8 + size
            if len(buffer) < total_frame_len:
                break

            payload = buffer[8:total_frame_len]
            buffer[:] = buffer[total_frame_len:]

            text = payload.decode("utf-8", errors="replace").rstrip("\r\n")
            if text:
                results.append((stream_id, text))

        return results
