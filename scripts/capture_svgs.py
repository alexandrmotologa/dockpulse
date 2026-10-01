"""Generate authentic terminal SVGs for DockPulse documentation."""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.table import Table

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.config import detect_docker_config
from dockpulse.core.container import group_containers_by_compose
from dockpulse.tui.app import DockPulseHUD


async def generate_tui_svgs() -> None:
    output_dir = Path("docs/images")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Main Dashboard HUD
    app = DockPulseHUD(config=detect_docker_config(demo=True))
    async with app.run_test(size=(140, 38)) as pilot:
        await pilot.pause(0.6)
        app.save_screenshot(str(output_dir / "screenshot_main.svg"))
        print("[+] Captured screenshot_main.svg")

    # 2. Images Modal
    app = DockPulseHUD(config=detect_docker_config(demo=True))
    async with app.run_test(size=(140, 38)) as pilot:
        await pilot.pause(0.6)
        app.action_open_images()
        await pilot.pause(0.5)
        app.save_screenshot(str(output_dir / "screenshot_images.svg"))
        print("[+] Captured screenshot_images.svg")

    # 3. Volumes Modal
    app = DockPulseHUD(config=detect_docker_config(demo=True))
    async with app.run_test(size=(140, 38)) as pilot:
        await pilot.pause(0.6)
        app.action_open_volumes()
        await pilot.pause(0.5)
        app.save_screenshot(str(output_dir / "screenshot_volumes.svg"))
        print("[+] Captured screenshot_volumes.svg")

    # 4. Theme Modal
    app = DockPulseHUD(config=detect_docker_config(demo=True))
    async with app.run_test(size=(140, 38)) as pilot:
        await pilot.pause(0.6)
        app.action_switch_theme()
        await pilot.pause(0.5)
        app.save_screenshot(str(output_dir / "screenshot_theme.svg"))
        print("[+] Captured screenshot_theme.svg")

    # 5. Inspect & Healthchecks Modal
    app = DockPulseHUD(config=detect_docker_config(demo=True))
    async with app.run_test(size=(140, 38)) as pilot:
        await pilot.pause(0.6)
        conts = await app.api_client.list_containers(all_containers=True)
        if conts:
            app._active_container = conts[0]
        await app.action_inspect_container()
        await pilot.pause(0.5)
        app.save_screenshot(str(output_dir / "screenshot_inspect.svg"))
        print("[+] Captured screenshot_inspect.svg")


async def generate_cli_svg() -> None:
    output_dir = Path("docs/images")
    console = Console(record=True, width=128)

    config = detect_docker_config(demo=True)
    client = DockerApiClient(config=config)
    async with client:
        containers = await client.list_containers(all_containers=True)
        projects, _ = group_containers_by_compose(containers)

        table = Table(
            title="Docker Compose Project Stacks",
            border_style="#334155",
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Stack / Project", style="bold white", width=24)
        table.add_column("Service", style="cyan", width=22)
        table.add_column("Status", width=14)
        table.add_column("Container ID", style="dim", width=14)
        table.add_column("Ports", style="dim green")

        for proj in sorted(projects, key=lambda p: p.name):
            for c in proj.containers:
                status_style = "green" if c.is_running else "red" if c.is_exited else "yellow"
                table.add_row(
                    proj.name,
                    c.compose_service or c.primary_name,
                    f"[{status_style}]{c.status}[/]",
                    c.short_id,
                    c.ports_summary,
                )

        console.print("[bold cyan]$ dockpulse compose ps[/]\n")
        console.print(table)

        # Container process table (top)
        top_data = await client.get_container_top(containers[0].id)
        top_table = Table(
            title=f"Processes in {containers[0].primary_name} ({containers[0].short_id})",
            border_style="#334155",
            header_style="bold cyan",
            expand=True,
        )
        for t in top_data["Titles"]:
            top_table.add_column(t, style="white")
        for proc in top_data["Processes"]:
            top_table.add_row(*proc)

        console.print(f"\n[bold cyan]$ dockpulse top {containers[0].primary_name}[/]\n")
        console.print(top_table)

        console.save_svg(str(output_dir / "screenshot_cli.svg"), title="dockpulse CLI Suite")
        print("[+] Captured screenshot_cli.svg")


async def main() -> None:
    await generate_tui_svgs()
    await generate_cli_svg()
    print("All SVGs captured successfully.")


if __name__ == "__main__":
    asyncio.run(main())
