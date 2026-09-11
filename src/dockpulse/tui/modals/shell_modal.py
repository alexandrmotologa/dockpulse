"""Interactive command execution modal screen."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, RichLog, Static

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.core.container import ContainerModel


class ShellModal(ModalScreen[None]):
    """Modal dialog to execute commands inside a running container."""

    DEFAULT_CSS = """
    ShellModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #shell-container {
        width: 84;
        height: 80%;
        background: #0f172a;
        border: thick #38bdf8;
        padding: 1 2;
        layout: vertical;
    }
    #shell-title {
        text-style: bold;
        color: #38bdf8;
        margin-bottom: 1;
    }
    #shell-input {
        margin-bottom: 1;
        background: #1e293b;
        color: #f1f5f9;
        border: tall #334155;
    }
    #shell-input:focus {
        border: tall #38bdf8;
    }
    #shell-output {
        height: 1fr;
        background: #050811;
        border: solid #334155;
        scrollbar-gutter: stable;
        margin-bottom: 1;
    }
    #button-bar {
        height: 3;
        align: right middle;
    }
    #button-bar Button {
        margin-left: 1;
    }
    """

    def __init__(self, api_client: DockerApiClient, container: ContainerModel) -> None:
        super().__init__()
        self.api_client = api_client
        self.container = container

    def compose(self) -> ComposeResult:
        with Vertical(id="shell-container"):
            yield Static(f"💻 Execute Command in {self.container.primary_name}", id="shell-title")
            yield Input(
                placeholder="Enter command (e.g. sh, uname -a, ps aux)...",
                id="shell-input",
                value="uname -a",
            )
            yield RichLog(id="shell-output", markup=True, highlight=True, auto_scroll=True)
            with Horizontal(id="button-bar"):
                yield Button("Run Command", id="run-btn", variant="success")
                yield Button("Close (Esc)", id="close-btn", variant="default")

    def on_mount(self) -> None:
        output = self.query_one("#shell-output", RichLog)
        output.write(
            f"[dim]Ready to execute in container {self.container.primary_name} ({self.container.short_id}). Press Enter or Run.[/]"
        )
        self.query_one("#shell-input", Input).focus()

    @on(Input.Submitted, "#shell-input")
    async def _on_input_submitted(self) -> None:
        await self._run_current_command()

    @on(Button.Pressed, "#run-btn")
    async def _on_run_pressed(self) -> None:
        await self._run_current_command()

    @on(Button.Pressed, "#close-btn")
    def _on_close_pressed(self) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()

    async def _run_current_command(self) -> None:
        cmd_input = self.query_one("#shell-input", Input)
        output = self.query_one("#shell-output", RichLog)

        cmd_str = cmd_input.value.strip()
        if not cmd_str:
            return

        cmd_parts = cmd_str.split()
        output.write(f"\n[bold cyan]$ {cmd_str}[/]")

        try:
            exec_id = await self.api_client.create_exec(
                self.container.id,
                cmd=cmd_parts,
                tty=True,
                stdin=False,
            )
            async for chunk in self.api_client.start_exec(exec_id, tty=True):
                text = chunk.decode("utf-8", errors="replace").rstrip("\r\n")
                if text:
                    output.write(text)
        except Exception as err:
            output.write(f"[bold red]Execution error: {err}[/]")
