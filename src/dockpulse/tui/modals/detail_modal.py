"""Container inspection and metadata modal screen."""

from typing import Any

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class DetailModal(ModalScreen[None]):
    """Modal dialog displaying detailed container inspection metadata."""

    DEFAULT_CSS = """
    DetailModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #detail-container {
        width: 80;
        height: 80%;
        background: #0f172a;
        border: thick #38bdf8;
        padding: 1 2;
        layout: vertical;
    }
    #detail-scroll {
        height: 1fr;
    }
    #detail-title {
        text-style: bold;
        color: #38bdf8;
        margin-bottom: 1;
    }
    #close-btn {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, inspect_data: dict[str, Any]) -> None:
        super().__init__()
        self.data = inspect_data

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            name = self.data.get("Name", "").lstrip("/") or self.data.get("Id", "")[:12]
            yield Static(f"📦 Container Details: {name}", id="detail-title")
            with VerticalScroll(id="detail-scroll"):
                yield Static(self._build_content())
            yield Button("Close (Esc)", id="close-btn", variant="primary")

    def _build_content(self) -> Table:
        table = Table(box=None, expand=True, padding=(0, 1))
        table.add_column("Property", style="bold cyan", width=18)
        table.add_column("Value", style="white")

        table.add_row("ID", self.data.get("Id", "-"))
        table.add_row("Image", self.data.get("Image", "-"))
        table.add_row(
            "State",
            self.data.get("State", "-")
            if isinstance(self.data.get("State"), str)
            else str(self.data.get("State", {}).get("Status", "-")),
        )
        table.add_row("Status", self.data.get("Status", "-"))

        config = self.data.get("Config", {})
        cmd = config.get("Cmd") or self.data.get("Command")
        table.add_row("Command", " ".join(cmd) if isinstance(cmd, list) else str(cmd or "-"))

        # Network
        net = self.data.get("NetworkSettings", {})
        ip = net.get("IPAddress") or "-"
        table.add_row("IP Address", ip)

        # Ports
        ports = self.data.get("Ports", [])
        if ports:
            p_text = Text()
            for p in ports:
                if isinstance(p, dict):
                    pub = p.get("PublicPort")
                    priv = p.get("PrivatePort")
                    ptype = p.get("Type", "tcp")
                    p_text.append(f"{pub}:{priv}/{ptype}  " if pub else f"{priv}/{ptype}  ")
            table.add_row("Ports", p_text)

        # Mounts
        mounts = self.data.get("Mounts", [])
        if mounts:
            m_text = Text()
            for m in mounts:
                src = m.get("Source", "-")
                dest = m.get("Destination", "-")
                m_text.append(f"{src} -> {dest}\n")
            table.add_row("Mounts", m_text)

        # Env vars
        env_list = config.get("Env", [])
        if env_list:
            e_text = Text()
            for env in env_list[:12]:
                e_text.append(f"{env}\n")
            if len(env_list) > 12:
                e_text.append(f"... (+{len(env_list) - 12} more)\n", style="dim")
            table.add_row("Environment", e_text)

        return table

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()
