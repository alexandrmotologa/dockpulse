"""Volumes management modal screen."""

from typing import Any

from rich.table import Table
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.core.stats_streamer import format_bytes


class VolumesModal(ModalScreen[None]):
    """Modal dialog for inspecting and pruning Docker volumes."""

    DEFAULT_CSS = """
    VolumesModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #volumes-box {
        width: 86;
        height: 80%;
        background: #0f172a;
        border: thick #38bdf8;
        padding: 1 2;
        layout: vertical;
    }
    #volumes-scroll {
        height: 1fr;
        margin: 1 0;
    }
    #volumes-title {
        text-style: bold;
        color: #38bdf8;
    }
    #volumes-buttons {
        height: 3;
        align: right middle;
    }
    #volumes-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, api_client: DockerApiClient) -> None:
        super().__init__()
        self.api_client = api_client
        self._volumes: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="volumes-box"):
            yield Static("💾 Local Docker Volumes", id="volumes-title")
            with VerticalScroll(id="volumes-scroll"):
                yield Static("Loading volumes...", id="volumes-table")
            with Horizontal(id="volumes-buttons"):
                yield Button("Prune Orphan Volumes", id="prune-orphan-btn", variant="error")
                yield Button("Close (Esc)", id="close-btn", variant="default")

    async def on_mount(self) -> None:
        await self._load_volumes()

    async def _load_volumes(self) -> None:
        table_static = self.query_one("#volumes-table", Static)
        try:
            self._volumes = await self.api_client.list_volumes()
            table_static.update(self._build_table())
        except Exception as err:
            table_static.update(f"[bold red]Failed to list volumes: {err}[/]")

    def _build_table(self) -> Table:
        table = Table(box=None, expand=True, padding=(0, 1))
        table.add_column("Volume Name", style="bold white")
        table.add_column("Driver", style="dim cyan", width=10)
        table.add_column("Size", justify="right", style="bold yellow", width=12)
        table.add_column("Status", width=14)

        for vol in self._volumes:
            name = vol.get("Name", "-")
            driver = vol.get("Driver", "local")
            usage = vol.get("UsageData", {}) or {}
            size_bytes = usage.get("Size", 0)
            ref_count = usage.get("RefCount", 0)
            is_in_use = ref_count > 0 or "pgdata" in name or "redisdata" in name

            status = "[green]In Use[/]" if is_in_use else "[bold red]Orphan[/]"
            table.add_row(name, driver, format_bytes(size_bytes), status)

        return table

    @on(Button.Pressed, "#prune-orphan-btn")
    async def _on_prune_orphan(self) -> None:
        for vol in self._volumes:
            name = vol.get("Name", "")
            usage = vol.get("UsageData", {}) or {}
            if usage.get("RefCount", 0) == 0 and not ("pgdata" in name or "redisdata" in name):
                try:
                    await self.api_client.remove_volume(name, force=True)
                except Exception:
                    pass
        await self._load_volumes()

    @on(Button.Pressed, "#close-btn")
    def _on_close(self) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()
