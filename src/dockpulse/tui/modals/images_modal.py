"""Images management modal screen."""

from typing import Any

from rich.table import Table
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.core.stats_streamer import format_bytes


class ImagesModal(ModalScreen[None]):
    """Modal dialog for browsing and managing local Docker images."""

    DEFAULT_CSS = """
    ImagesModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #images-box {
        width: 86;
        height: 80%;
        background: #0f172a;
        border: thick #38bdf8;
        padding: 1 2;
        layout: vertical;
    }
    #images-scroll {
        height: 1fr;
        margin: 1 0;
    }
    #images-title {
        text-style: bold;
        color: #38bdf8;
    }
    #images-buttons {
        height: 3;
        align: right middle;
    }
    #images-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, api_client: DockerApiClient) -> None:
        super().__init__()
        self.api_client = api_client
        self._images: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="images-box"):
            yield Static("🖼️ Local Docker Images", id="images-title")
            with VerticalScroll(id="images-scroll"):
                yield Static("Loading images...", id="images-table")
            with Horizontal(id="images-buttons"):
                yield Button("Prune Dangling (<none>)", id="prune-dangling-btn", variant="warning")
                yield Button("Close (Esc)", id="close-btn", variant="default")

    async def on_mount(self) -> None:
        await self._load_images()

    async def _load_images(self) -> None:
        table_static = self.query_one("#images-table", Static)
        try:
            self._images = await self.api_client.list_images()
            table_static.update(self._build_table())
        except Exception as err:
            table_static.update(f"[bold red]Failed to list images: {err}[/]")

    def _build_table(self) -> Table:
        table = Table(box=None, expand=True, padding=(0, 1))
        table.add_column("Repository : Tag", style="bold white")
        table.add_column("Image ID", style="dim cyan", width=14)
        table.add_column("Size", justify="right", style="bold yellow", width=12)
        table.add_column("Status", width=12)

        for img in self._images:
            raw_id = img.get("Id", "")
            clean_id = raw_id.removeprefix("sha256:")[:12]
            tags = img.get("RepoTags") or ["<none>:<none>"]
            tag_display = ", ".join(tags)
            size_bytes = img.get("Size", 0)
            is_dangling = "<none>" in tag_display

            status = "[bold red]Dangling[/]" if is_dangling else "[green]In Use[/]"
            table.add_row(tag_display, clean_id, format_bytes(size_bytes), status)

        return table

    @on(Button.Pressed, "#prune-dangling-btn")
    async def _on_prune_dangling(self) -> None:
        dangling = [img for img in self._images if "<none>" in ", ".join(img.get("RepoTags") or [])]
        for img in dangling:
            raw_id = img.get("Id", "")
            try:
                await self.api_client.remove_image(raw_id, force=True)
            except Exception:
                pass
        await self._load_images()

    @on(Button.Pressed, "#close-btn")
    def _on_close(self) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()
