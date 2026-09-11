"""Live streaming log tail widget with demultiplexed colors, search, and auto-scroll control."""

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static

from dockpulse.core.log_multiplexer import LogLine, LogMultiplexer


class LogTailWidget(Widget):
    """Container log tailing widget with search filter and pause/resume scroll locking."""

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
        self._multiplexer = LogMultiplexer(max_lines=1500)
        self._auto_scroll = True
        self._active_query: str = ""

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
        if not self._active_query or self._matches_filter(line):
            rich_log.write(line.render_markup())

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
        if not self._active_query:
            return True
        return self._active_query.lower() in line.text.lower()

    def _replay_filtered_logs(self) -> None:
        rich_log = self.query_one("#rich-log-box", RichLog)
        rich_log.clear()
        lines = self._multiplexer.get_lines(self._active_query if self._active_query else None)
        for line in lines:
            rich_log.write(line.render_markup())
        self._update_header()

    def _update_header(self) -> None:
        header = self.query_one("#log-header", Static)
        text = Text()
        text.append("LOG STREAM ", style="bold cyan")
        scroll_status = "ON" if self._auto_scroll else "PAUSED"
        scroll_style = "bold green" if self._auto_scroll else "bold yellow"
        text.append(f"[Auto-scroll: {scroll_status}] ", style=scroll_style)
        text.append(f"[Total: {self._multiplexer.count}]  ", style="dim")
        text.append("Keys: Space (pause/scroll) | c (clear) | / (search)", style="dim italic")
        header.update(text)
