"""Disk hygiene and container prune confirmation modal screen."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.core.stats_streamer import format_bytes


class PruneModal(ModalScreen[bool]):
    """Confirmation modal dialog for pruning stopped containers."""

    DEFAULT_CSS = """
    PruneModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #prune-box {
        width: 60;
        height: auto;
        background: #0f172a;
        border: thick #ef4444;
        padding: 1 2;
    }
    #prune-title {
        text-style: bold;
        color: #ef4444;
        margin-bottom: 1;
    }
    #prune-body {
        margin-bottom: 1;
        color: #f1f5f9;
    }
    #prune-buttons {
        height: 3;
        align: right middle;
    }
    #prune-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, api_client: DockerApiClient) -> None:
        super().__init__()
        self.api_client = api_client

    def compose(self) -> ComposeResult:
        with Vertical(id="prune-box"):
            yield Static("⚠️ Prune Stopped Containers", id="prune-title")
            yield Static(
                "This action will remove all stopped containers.\n"
                "Running containers will not be affected.\n\n"
                "Are you sure you want to proceed?",
                id="prune-body",
            )
            with Horizontal(id="prune-buttons"):
                yield Button("Prune Now", id="confirm-btn", variant="error")
                yield Button("Cancel (Esc)", id="cancel-btn", variant="default")

    @on(Button.Pressed, "#confirm-btn")
    async def _on_confirm(self) -> None:
        body = self.query_one("#prune-body", Static)
        body.update("Pruning containers in progress...")

        try:
            result = await self.api_client.prune_containers()
            reclaimed = result.get("SpaceReclaimed", 0)
            deleted = result.get("ContainersDeleted", [])
            count = len(deleted) if deleted else 0
            body.update(
                f"[bold green]Prune complete![/]\n"
                f"Removed {count} container(s).\n"
                f"Reclaimed {format_bytes(reclaimed)} of disk space."
            )
            self.query_one("#confirm-btn", Button).disabled = True
            self.query_one("#cancel-btn", Button).label = "Close"
        except Exception as err:
            body.update(f"[bold red]Failed to prune: {err}[/]")

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self) -> None:
        self.dismiss(True)

    def key_escape(self) -> None:
        self.dismiss(False)
