"""Live streaming log tail widget with demultiplexed colors, search, timestamps, and export."""

from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static

from dockpulse.core.log_multiplexer import LogLine, LogMultiplexer


class LogTailWidget(Widget):
    """Container log tailing widget with search filter, timestamps, level filter, and file export."""

    DEFAULT_CSS = """
    LogTailWidget {
        height: 1fr;
        background: #050811;
        layout: vertical;
        padding: 0 1;
    }
    #log-header {
        height: 1;
        background: #090d16;
        color: #94a3b8;
    }
    #log-filter-input {
        height: 3;
        margin: 0 0 1 0;
        background: #0f172a;
        border: tall #334155;
        color: #f1f5f9;
        display: none;
    }
    #log-filter-input:focus {
        border: tall #38bdf8;
    }
    #rich-log-box {
        height: 1fr;
        background: #050811;
        scrollbar-gutter: stable;
        border: solid #1e293b;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._multiplexer = LogMultiplexer(max_lines=2000)
        self._auto_scroll = True
        self._active_query: str = ""
        self._show_timestamps: bool = True
        self._severity_filter: str | None = (
            None  # None: ALL, "WARN": Warn/Error, "ERROR": Error only
        )

    def compose(self) -> ComposeResult:
        yield Static("", id="log-header")
        yield Input(placeholder="Filter logs (regex or text)...", id="log-filter-input")
        yield RichLog(id="rich-log-box", highlight=False, markup=True, auto_scroll=True)

    def on_mount(self) -> None:
        self._update_header()

    def add_log_line(self, stream_id: int, text: str) -> None:
        """Receive a new log line from the Docker log stream."""
        line = self._multiplexer.add_line(stream_id, text)
        rich_log = self.query_one("#rich-log-box", RichLog)

        # Check filter condition
        if self._matches_filter(line):
            rich_log.write(line.render_markup(show_timestamp=self._show_timestamps))

        self._update_header()

    def clear(self) -> None:
        """Clear log buffer and display."""
        self._multiplexer.clear()
        rich_log = self.query_one("#rich-log-box", RichLog)
        rich_log.clear()
        self._update_header()

    def toggle_auto_scroll(self) -> bool:
        """Toggle auto-scroll lock."""
        self._auto_scroll = not self._auto_scroll
        rich_log = self.query_one("#rich-log-box", RichLog)
        rich_log.auto_scroll = self._auto_scroll
        self._update_header()
        return self._auto_scroll

    def toggle_timestamps(self) -> bool:
        """Toggle timestamp visibility."""
        self._show_timestamps = not self._show_timestamps
        self._replay_filtered_logs()
        return self._show_timestamps

    def cycle_severity_filter(self) -> str:
        """Cycle through log severity filters: ALL -> WARN+ -> ERROR ONLY -> ALL."""
        if self._severity_filter is None:
            self._severity_filter = "WARN"
            label = "WARN+"
        elif self._severity_filter == "WARN":
            self._severity_filter = "ERROR"
            label = "ERROR ONLY"
        else:
            self._severity_filter = None
            label = "ALL"

        self._replay_filtered_logs()
        return label

    def export_logs_to_file(self, container_name: str = "container") -> tuple[Path, int]:
        """Export stored logs to a timestamped file in the working directory."""
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = container_name.replace("/", "").replace(":", "_")
        filename = Path(f"dockpulse_{safe_name}_{now_str}.log")
        count = self._multiplexer.export_to_file(filename)
        return filename.resolve(), count

    def toggle_search_bar(self) -> None:
        """Toggle visibility of the search input."""
        inp = self.query_one("#log-filter-input", Input)
        if inp.styles.display == "none":
            inp.styles.display = "block"
            inp.focus()
        else:
            inp.styles.display = "none"
            rich_log = self.query_one("#rich-log-box", RichLog)
            rich_log.focus()

    @on(Input.Changed, "#log-filter-input")
    def _on_filter_changed(self, event: Input.Changed) -> None:
        self._active_query = event.value.strip()
        self._replay_filtered_logs()

    @on(Input.Submitted, "#log-filter-input")
    def _on_filter_submitted(self) -> None:
        rich_log = self.query_one("#rich-log-box", RichLog)
        rich_log.focus()

    def _matches_filter(self, line: LogLine) -> bool:
        if self._severity_filter == "ERROR" and line.severity != "ERROR":
            return False
        if self._severity_filter == "WARN" and line.severity not in ("ERROR", "WARN"):
            return False
        if self._active_query and self._active_query.lower() not in line.text.lower():
            return False
        return True

    def _replay_filtered_logs(self) -> None:
        rich_log = self.query_one("#rich-log-box", RichLog)
        rich_log.clear()
        lines = self._multiplexer.get_lines(
            query=self._active_query if self._active_query else None,
            min_severity=self._severity_filter,
        )
        for line in lines:
            rich_log.write(line.render_markup(show_timestamp=self._show_timestamps))
        self._update_header()

    def _update_header(self) -> None:
        header = self.query_one("#log-header", Static)
        text = Text()
        text.append("LOG STREAM ", style="bold cyan")

        scroll_status = "ON" if self._auto_scroll else "PAUSED"
        scroll_style = "bold green" if self._auto_scroll else "bold yellow"
        text.append(f"[Auto-scroll: {scroll_status}] ", style=scroll_style)

        ts_status = "ON" if self._show_timestamps else "OFF"
        text.append(f"[TS: {ts_status}] ", style="bold blue" if self._show_timestamps else "dim")

        sev_label = "ALL"
        if self._severity_filter == "WARN":
            sev_label = "WARN+"
        elif self._severity_filter == "ERROR":
            sev_label = "ERROR ONLY"
        text.append(
            f"[Level: {sev_label}] ", style="bold magenta" if self._severity_filter else "dim"
        )

        text.append(f"[Lines: {self._multiplexer.count}]  ", style="dim")
        text.append(
            "Keys: t (TS) | l (Level) | Space (Pause) | Ctrl+S (Export)", style="dim italic"
        )
        header.update(text)
