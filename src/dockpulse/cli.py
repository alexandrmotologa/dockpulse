import asyncio
import sys
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Configure standard streams for UTF-8 on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dockpulse import __version__
from dockpulse.client.docker_api import DockerApiClient
from dockpulse.config import detect_docker_config
from dockpulse.core.container import group_containers_by_compose
from dockpulse.core.stats_streamer import ContainerStatsCalculator, format_bytes

app = typer.Typer(
    name="dockpulse",
    help="High-speed keyboard-driven terminal HUD and CLI for Docker and Compose.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]dockpulse[/] v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
    demo: Annotated[
        bool,
        typer.Option("--demo", help="Run in demo mode with simulated microservice containers."),
    ] = False,
    socket: Annotated[
        Optional[str],
        typer.Option("--socket", "-s", help="Custom Docker socket path or TCP URL."),
    ] = None,
) -> None:
    """Launch the interactive terminal HUD by default when no subcommand is specified."""
    if ctx.invoked_subcommand is None:
        _run_tui(socket_override=socket, demo=demo)


@app.command("hud")
def hud_command(
    demo: Annotated[bool, typer.Option("--demo", help="Run with simulated microservices.")] = False,
    socket: Annotated[
        Optional[str], typer.Option("--socket", "-s", help="Custom Docker socket path.")
    ] = None,
) -> None:
    """Launch the interactive terminal HUD."""
    _run_tui(socket_override=socket, demo=demo)


def _run_tui(socket_override: Optional[str] = None, demo: bool = False) -> None:
    """Start the Textual HUD app."""
    from dockpulse.tui.app import DockPulseHUD

    config = detect_docker_config(socket_override=socket_override, demo=demo)
    hud_app = DockPulseHUD(config=config)
    hud_app.run()


@app.command("ps")
def ps_command(
    all_containers: Annotated[
        bool, typer.Option("--all", "-a", help="Show all containers including stopped.")
    ] = True,
    demo: Annotated[bool, typer.Option("--demo", help="Run in demo mode.")] = False,
    socket: Annotated[
        Optional[str], typer.Option("--socket", "-s", help="Docker socket path.")
    ] = None,
) -> None:
    """List containers grouped by Compose project in a formatted table."""
    asyncio.run(_async_ps(all_containers=all_containers, demo=demo, socket=socket))


async def _async_ps(all_containers: bool, demo: bool, socket: Optional[str]) -> None:
    config = detect_docker_config(socket_override=socket, demo=demo)
    client = DockerApiClient(config=config)

    async with client:
        try:
            containers = await client.list_containers(all_containers=all_containers)
        except Exception as err:
            console.print(f"[bold red]Failed to connect to Docker engine:[/] {err}")
            console.print(
                "[dim]Tip: Pass [bold]--demo[/] to explore DockPulse without a running daemon.[/]"
            )
            raise typer.Exit(code=1) from err

    if not containers:
        console.print("[yellow]No containers found.[/]")
        return

    projects, standalone = group_containers_by_compose(containers)

    table = Table(
        title="DockPulse Containers",
        border_style="#334155",
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Status", width=14)
    table.add_column("Project", style="bold blue", width=18)
    table.add_column("Service / Name", style="white")
    table.add_column("ID", style="dim", width=14)
    table.add_column("Image", style="dim cyan")
    table.add_column("Ports", style="dim yellow")

    for proj in projects:
        for cont in proj.containers:
            table.add_row(
                cont.status_badge,
                proj.name,
                cont.compose_service or cont.primary_name,
                cont.short_id,
                cont.image,
                cont.ports_summary,
            )

    for cont in standalone:
        table.add_row(
            cont.status_badge,
            "[dim]standalone[/]",
            cont.primary_name,
            cont.short_id,
            cont.image,
            cont.ports_summary,
        )

    console.print(table)


@app.command("stats")
def stats_command(
    demo: Annotated[bool, typer.Option("--demo", help="Run in demo mode.")] = False,
    socket: Annotated[
        Optional[str], typer.Option("--socket", "-s", help="Docker socket path.")
    ] = None,
) -> None:
    """Display real-time resource telemetry snapshot for running containers."""
    asyncio.run(_async_stats(demo=demo, socket=socket))


async def _async_stats(demo: bool, socket: Optional[str]) -> None:
    config = detect_docker_config(socket_override=socket, demo=demo)
    client = DockerApiClient(config=config)

    async with client:
        try:
            containers = await client.list_containers(all_containers=False)
            running = [c for c in containers if c.is_running]
        except Exception as err:
            console.print(f"[bold red]Failed to connect to Docker engine:[/] {err}")
            raise typer.Exit(code=1) from err

        if not running:
            console.print("[yellow]No running containers found.[/]")
            return

        table = Table(
            title="Container Resource Snapshot",
            border_style="#334155",
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Container", style="bold white", width=28)
        table.add_column("CPU %", justify="right", style="bold cyan", width=10)
        table.add_column("Memory RSS", justify="right", style="bold yellow", width=14)
        table.add_column("Mem %", justify="right", width=8)
        table.add_column("Network I/O", style="dim", width=22)
        table.add_column("Block I/O", style="dim", width=22)

        calc = ContainerStatsCalculator()
        for cont in running[:10]:
            try:
                # Fetch single stats sample
                async for raw_stat in client.stream_stats(cont.id):
                    snap = calc.calculate(raw_stat)
                    table.add_row(
                        cont.primary_name,
                        f"{snap.cpu_percent:5.1f}%",
                        format_bytes(snap.memory_bytes),
                        f"{snap.memory_percent:5.1f}%",
                        f"▼{format_bytes(snap.net_rx_bytes)} ▲{format_bytes(snap.net_tx_bytes)}",
                        f"R:{format_bytes(snap.block_read_bytes)} W:{format_bytes(snap.block_write_bytes)}",
                    )
                    break
            except Exception:
                table.add_row(cont.primary_name, "-", "-", "-", "-", "-")

        console.print(table)


@app.command("logs")
def logs_command(
    target: Annotated[str, typer.Argument(help="Container name or container ID to inspect.")],
    tail: Annotated[int, typer.Option("--tail", "-n", help="Number of log lines to show.")] = 50,
    demo: Annotated[bool, typer.Option("--demo", help="Run in demo mode.")] = False,
    socket: Annotated[
        Optional[str], typer.Option("--socket", "-s", help="Docker socket path.")
    ] = None,
) -> None:
    """Tail and stream multiplexed logs for a container."""
    asyncio.run(_async_logs(target=target, tail=tail, demo=demo, socket=socket))


async def _async_logs(target: str, tail: int, demo: bool, socket: Optional[str]) -> None:
    config = detect_docker_config(socket_override=socket, demo=demo)
    client = DockerApiClient(config=config)

    async with client:
        try:
            containers = await client.list_containers(all_containers=True)
            matched = next(
                (c for c in containers if target in c.primary_name or target in c.id), None
            )
            if not matched:
                console.print(f"[bold red]Error:[/] No container matching '{target}' found.")
                raise typer.Exit(code=1)

            console.print(
                f"[bold cyan]Tailing logs for {matched.primary_name} ({matched.short_id}):[/]\n"
            )
            async for stream_id, text in client.stream_logs(matched.id, tail=tail, follow=False):
                if stream_id == 2:
                    console.print(f"[bold red]ERR[/] [red]{text}[/]")
                else:
                    console.print(f"[dim cyan]OUT[/] {text}")
        except Exception as err:
            console.print(f"[bold red]Log streaming failed:[/] {err}")
            raise typer.Exit(code=1) from err


@app.command("check")
def check_command(
    socket: Annotated[
        Optional[str], typer.Option("--socket", "-s", help="Custom Docker socket path.")
    ] = None,
) -> None:
    """Check Docker daemon connectivity and socket diagnostics."""
    asyncio.run(_async_check(socket=socket))


async def _async_check(socket: Optional[str]) -> None:
    config = detect_docker_config(socket_override=socket, demo=False)
    client = DockerApiClient(config=config)

    console.print(f"[bold]Target Socket:[/] {config.socket_path} ({config.socket_type})")
    console.print(f"[bold]Base URL:[/] {config.base_url}")

    async with client:
        is_alive = await client.ping()
        if is_alive:
            try:
                ver_info = await client.get_version()
                sys_info = await client.get_system_info()
                panel_text = Text()
                panel_text.append("[OK] Connection: OK\n", style="bold green")
                panel_text.append(f"Docker Version: {ver_info.get('Version')}\n")
                panel_text.append(f"API Version: {ver_info.get('ApiVersion')}\n")
                panel_text.append(f"OS/Arch: {ver_info.get('Os')}/{ver_info.get('Arch')}\n")
                panel_text.append(f"Total Containers: {sys_info.get('Containers')}\n")
                panel_text.append(f"Running Containers: {sys_info.get('ContainersRunning')}\n")
                console.print(
                    Panel(panel_text, title="Docker Engine Diagnostics", border_style="green")
                )
            except Exception as err:
                console.print(f"[bold yellow]Ping OK but failed to query metadata:[/] {err}")
        else:
            panel_text = Text()
            panel_text.append("[FAIL] Connection Failed\n", style="bold red")
            panel_text.append(
                f"Could not reach Docker engine at {config.socket_path}.\n\n", style="white"
            )
            panel_text.append("Suggestions:\n", style="bold yellow")
            panel_text.append("1. Verify Docker Desktop or dockerd is running.\n")
            panel_text.append("2. Test with demo mode: [bold cyan]dockpulse --demo[/]\n")
            panel_text.append("3. Specify custom socket: [bold cyan]dockpulse --socket <path>[/]\n")
            console.print(Panel(panel_text, title="Docker Engine Diagnostics", border_style="red"))


@app.command("prune")
def prune_command(
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt.")] = False,
    demo: Annotated[bool, typer.Option("--demo", help="Run in demo mode.")] = False,
    socket: Annotated[
        Optional[str], typer.Option("--socket", "-s", help="Docker socket path.")
    ] = None,
) -> None:
    """Remove stopped containers and reclaim disk space."""
    if not force:
        confirm = typer.confirm("Are you sure you want to remove all stopped containers?")
        if not confirm:
            console.print("[yellow]Prune cancelled.[/]")
            raise typer.Abort()

    asyncio.run(_async_prune(demo=demo, socket=socket))


async def _async_prune(demo: bool, socket: Optional[str]) -> None:
    config = detect_docker_config(socket_override=socket, demo=demo)
    client = DockerApiClient(config=config)

    async with client:
        try:
            res = await client.prune_containers()
            deleted = res.get("ContainersDeleted") or []
            reclaimed = res.get("SpaceReclaimed", 0)
            console.print(
                f"[bold green]Prune complete![/] Removed {len(deleted)} stopped container(s). "
                f"Reclaimed {format_bytes(reclaimed)} of disk space."
            )
        except Exception as err:
            console.print(f"[bold red]Prune failed:[/] {err}")
            raise typer.Exit(code=1) from err
