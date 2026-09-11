"""Top system header bar widget showing daemon metadata, container counts, and disk reclamation."""

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class HeaderBar(Widget):
    """Header bar displaying Docker daemon connectivity, container inventory, and disk statistics."""

    DEFAULT_CSS = """
    HeaderBar {
        height: 3;
        dock: top;
        background: #0f172a;
        color: #f8fafc;
        border-bottom: solid #334155;
        padding: 0 1;
        layout: horizontal;
    }
    #brand-title {
        width: 22;
        content-align: left middle;
        text-style: bold;
        color: #38bdf8;
    }
    #daemon-info {
        width: 1fr;
        content-align: left middle;
        color: #94a3b8;
    }
    #counts-summary {
        width: auto;
        content-align: right middle;
    }
    """

    engine_version: reactive[str] = reactive("Connecting...")
    socket_label: reactive[str] = reactive("")
    total_count: reactive[int] = reactive(0)
    running_count: reactive[int] = reactive(0)
    paused_count: reactive[int] = reactive(0)
    stopped_count: reactive[int] = reactive(0)
    reclaimable_space: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Static("⚡ DOCKPULSE", id="brand-title")
        yield Static("", id="daemon-info")
        yield Static("", id="counts-summary")

    def watch_engine_version(self, value: str) -> None:
        self._update_daemon_info()

    def watch_socket_label(self, value: str) -> None:
        self._update_daemon_info()

    def watch_total_count(self, value: int) -> None:
        self._update_counts()

    def watch_running_count(self, value: int) -> None:
        self._update_counts()

    def watch_paused_count(self, value: int) -> None:
        self._update_counts()

    def watch_stopped_count(self, value: int) -> None:
        self._update_counts()

    def watch_reclaimable_space(self, value: str) -> None:
        self._update_counts()

    def _update_daemon_info(self) -> None:
        static = self.query_one("#daemon-info", Static)
        text = Text()
        text.append("Engine: ", style="dim")
        text.append(f"{self.engine_version}  ", style="bold white")
        text.append("Socket: ", style="dim")
        text.append(self.socket_label, style="cyan")
        static.update(text)

    def _update_counts(self) -> None:
        static = self.query_one("#counts-summary", Static)
        text = Text()
        text.append(f"Total: {self.total_count}  ", style="bold white")
        text.append(f"🟢 {self.running_count}  ", style="bold green")
        if self.paused_count > 0:
            text.append(f"⏸️ {self.paused_count}  ", style="bold yellow")
        text.append(
            f"🔴 {self.stopped_count}  ", style="bold red" if self.stopped_count > 0 else "dim"
        )
        if self.reclaimable_space:
            text.append(f"💾 Reclaimable: {self.reclaimable_space}", style="dim yellow")
        static.update(text)
