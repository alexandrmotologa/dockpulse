"""Multiplexed Docker log parsing, stdout/stderr framing, severity detection, and export."""

import re
import struct
from collections import deque
from dataclasses import dataclass
from pathlib import Path

ISO_TS_REGEX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s*"
)
BRACKET_TS_REGEX = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]\s*"
)


@dataclass
class LogLine:
    """Single demultiplexed log entry with stream source, timestamp, and severity classification."""

    stream_id: int  # 1: stdout, 2: stderr
    text: str
    timestamp: str | None = None
    clean_text: str = ""
    severity: str = "INFO"

    def __post_init__(self) -> None:
        raw = self.text

        # Extract timestamp if present at beginning of line
        m_bracket = BRACKET_TS_REGEX.match(raw)
        m_iso = ISO_TS_REGEX.match(raw)

        if m_bracket:
            self.timestamp = m_bracket.group(1)
            self.clean_text = raw[m_bracket.end() :]
        elif m_iso:
            self.timestamp = m_iso.group(1)
            self.clean_text = raw[m_iso.end() :]
        else:
            self.clean_text = raw

        # Classify severity
        text_upper = raw.upper()
        if (
            self.stream_id == 2
            or "ERROR" in text_upper
            or "FATAL" in text_upper
            or "EXCEPTION" in text_upper
            or "PANIC" in text_upper
        ):
            self.severity = "ERROR"
        elif "WARN" in text_upper:
            self.severity = "WARN"
        elif "DEBUG" in text_upper or "TRACE" in text_upper:
            self.severity = "DEBUG"
        else:
            self.severity = "INFO"

    @property
    def is_stderr(self) -> bool:
        return self.stream_id == 2

    @property
    def stream_name(self) -> str:
        return "STDERR" if self.is_stderr else "STDOUT"

    def render_markup(self, show_timestamp: bool = True) -> str:
        """Render formatted line with Rich console markup tags."""
        body = self.text if show_timestamp or not self.timestamp else self.clean_text
        escaped = body.replace("[", "\\[").replace("]", "\\]")

        ts_prefix = ""
        if show_timestamp and self.timestamp:
            ts_prefix = f"[dim]{self.timestamp}[/] "

        if self.severity == "ERROR":
            return f"{ts_prefix}[bold red]ERR[/] [red]{escaped}[/]"
        if self.severity == "WARN":
            return f"{ts_prefix}[bold yellow]WRN[/] [yellow]{escaped}[/]"
        if self.severity == "DEBUG":
            return f"{ts_prefix}[dim blue]DBG[/] [dim]{escaped}[/]"
        return f"{ts_prefix}[dim cyan]OUT[/] {escaped}"


class LogMultiplexer:
    """Manages container log history, framing demultiplexing, filtering, and disk export."""

    def __init__(self, max_lines: int = 1500) -> None:
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

    def get_lines(
        self,
        query: str | None = None,
        min_severity: str | None = None,
    ) -> list[LogLine]:
        """Return lines, optionally filtered by search text and minimum severity."""
        result = list(self._lines)

        if min_severity:
            min_sev = min_severity.upper()
            if min_sev == "ERROR":
                result = [line for line in result if line.severity == "ERROR"]
            elif min_sev == "WARN":
                result = [line for line in result if line.severity in ("ERROR", "WARN")]

        if not query:
            return result

        try:
            pattern = re.compile(query, re.IGNORECASE)
            return [line for line in result if pattern.search(line.text)]
        except re.error:
            q_lower = query.lower()
            return [line for line in result if q_lower in line.text.lower()]

    def export_text(self) -> str:
        """Export raw unformatted logs as a single string."""
        return "\n".join(f"[{line.stream_name}] {line.text}" for line in self._lines)

    def export_to_file(self, target_path: str | Path) -> int:
        """Save stored log history to a local file.

        Returns:
            Number of lines written.
        """
        path = Path(target_path)
        content = self.export_text()
        path.write_text(content, encoding="utf-8")
        return len(self._lines)

    @staticmethod
    def parse_docker_frames(buffer: bytearray) -> list[tuple[int, str]]:
        """Parse Docker 8-byte framed byte buffers into (stream_id, text) tuples."""
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
