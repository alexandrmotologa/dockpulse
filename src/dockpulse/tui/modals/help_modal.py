"""Help and keyboard shortcuts modal screen."""

from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class HelpModal(ModalScreen[None]):
    """Modal dialog displaying keyboard navigation and operational shortcuts."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #help-container {
        width: 68;
        height: auto;
        max-height: 85%;
        background: #0f172a;
        border: thick #38bdf8;
        padding: 1 2;
    }
    #help-title {
        text-style: bold;
        color: #38bdf8;
        text-align: center;
        margin-bottom: 1;
    }
    #close-btn {
        margin-top: 1;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static("⚡ DockPulse — Keyboard Shortcuts", id="help-title")
            yield Static(self._build_table())
            yield Button("Close (Esc)", id="close-btn", variant="primary")

    def _build_table(self) -> Table:
        table = Table(box=None, expand=True, padding=(0, 1))
        table.add_column("Key", style="bold cyan", width=16)
        table.add_column("Action", style="white")

        table.add_row("Up / Down", "Navigate container tree")
        table.add_row("Enter", "Expand Compose group or select container")
        table.add_row("r", "Restart highlighted container")
        table.add_row("s", "Stop highlighted container")
        table.add_row("p", "Pause or unpause highlighted container")
        table.add_row("x", "Remove stopped container")
        table.add_row("d", "Inspect container details (ports, env, mounts)")
        table.add_row("e", "Execute command inside container")
        table.add_row("/", "Filter containers or search log stream")
        table.add_row("Space", "Pause or resume live log autoscroll")
        table.add_row("c", "Clear current log buffer")
        table.add_row("Tab", "Switch focus between panels")
        table.add_row("?", "Show this help screen")
        table.add_row("q / Ctrl+C", "Exit DockPulse")

        return table

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()
