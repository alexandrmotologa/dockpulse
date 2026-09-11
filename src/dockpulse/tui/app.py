"""Main Textual application for the DockPulse terminal HUD."""

import asyncio
import webbrowser

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical

from dockpulse.client.docker_api import DockerApiClient
from dockpulse.config import DockerConfig, detect_docker_config
from dockpulse.core.clipboard import copy_to_clipboard
from dockpulse.core.container import ContainerModel
from dockpulse.core.stats_streamer import ContainerStatsCalculator, format_bytes
from dockpulse.core.theme import THEMES, ThemePalette, get_theme
from dockpulse.tui.modals.detail_modal import DetailModal
from dockpulse.tui.modals.help_modal import HelpModal
from dockpulse.tui.modals.images_modal import ImagesModal
from dockpulse.tui.modals.prune_modal import PruneModal
from dockpulse.tui.modals.shell_modal import ShellModal
from dockpulse.tui.modals.theme_modal import ThemeModal
from dockpulse.tui.modals.volumes_modal import VolumesModal
from dockpulse.tui.widgets.container_tree import ContainerTreeWidget
from dockpulse.tui.widgets.header_bar import HeaderBar
from dockpulse.tui.widgets.log_tail import LogTailWidget
from dockpulse.tui.widgets.sparkline_panel import SparklinePanel


class DockPulseHUD(App[None]):
    """High-speed Docker & Compose Terminal HUD."""

    CSS = THEMES["default"].generate_css()

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "restart_container", "Restart", show=True),
        Binding("s", "stop_container", "Stop", show=True),
        Binding("p", "pause_container", "Pause", show=True),
        Binding("x", "remove_container", "Remove", show=True),
        Binding("R", "restart_project", "Restart Stack", show=True),
        Binding("S", "stop_project", "Stop Stack", show=True),
        Binding("o", "open_browser", "Open Web", show=True),
        Binding("y", "copy_clipboard", "Copy URI", show=True),
        Binding("d", "inspect_container", "Inspect", show=True),
        Binding("e", "exec_shell", "Exec", show=True),
        Binding("t", "toggle_timestamps", "Toggle TS", show=True),
        Binding("l", "cycle_log_level", "Log Level", show=True),
        Binding("ctrl+s", "export_logs", "Export", show=True),
        Binding("i", "open_images", "Images", show=True),
        Binding("v", "open_volumes", "Volumes", show=True),
        Binding("T", "switch_theme", "Themes", show=True),
        Binding("slash", "search", "Search", show=True),
        Binding("space", "toggle_scroll", "Pause Logs", show=True),
        Binding("c", "clear_logs", "Clear", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
    ]

    TITLE = "DockPulse HUD"
    SUB_TITLE = "Direct Docker Socket HUD"

    def __init__(
        self,
        config: DockerConfig | None = None,
        api_client: DockerApiClient | None = None,
        theme_name: str = "default",
    ) -> None:
        super().__init__()
        self.config = config or detect_docker_config()
        self.api_client = api_client or DockerApiClient(config=self.config)
        self.active_palette: ThemePalette = get_theme(theme_name)

        self._active_container: ContainerModel | None = None
        self._stats_task: asyncio.Task[None] | None = None
        self._logs_task: asyncio.Task[None] | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._stats_calc = ContainerStatsCalculator()

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with Horizontal(id="main-body"):
            yield ContainerTreeWidget()
            with Vertical(id="content-pane"):
                yield SparklinePanel()
                yield LogTailWidget()

    async def on_mount(self) -> None:
        """Initialize connection, fetch daemon info, and start background telemetry."""
        header = self.query_one(HeaderBar)
        header.socket_label = "[DEMO MODE]" if self.config.is_demo else self.config.socket_path

        # Check daemon availability
        is_connected = await self.api_client.ping()
        if not is_connected:
            self.notify(
                "Unable to connect to Docker daemon socket. Launch with --demo for simulated mode.",
                title="Connection Warning",
                severity="warning",
                timeout=8,
            )
            header.engine_version = "Disconnected"
        else:
            try:
                version_info = await self.api_client.get_version()
                ver = version_info.get("Version", "Unknown")
                api_ver = version_info.get("ApiVersion", "")
                header.engine_version = f"v{ver} (API {api_ver})"
            except Exception:
                header.engine_version = "Connected"

        await self._refresh_containers()
        await self._refresh_disk_usage()

        # Start periodic polling task for container list and count updates
        self._refresh_task = asyncio.create_task(self._periodic_inventory_refresh())

    async def on_unmount(self) -> None:
        """Clean up streaming tasks and close API client."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        if self._stats_task and not self._stats_task.done():
            self._stats_task.cancel()
        if self._logs_task and not self._logs_task.done():
            self._logs_task.cancel()
        await self.api_client.aclose()

    async def _refresh_containers(self) -> None:
        """Query Docker daemon for active containers and update tree and header counts."""
        try:
            containers = await self.api_client.list_containers(all_containers=True)
        except Exception:
            containers = []

        header = self.query_one(HeaderBar)
        header.total_count = len(containers)
        header.running_count = sum(1 for c in containers if c.is_running)
        header.paused_count = sum(1 for c in containers if c.is_paused)
        header.stopped_count = sum(1 for c in containers if c.is_exited)

        tree = self.query_one(ContainerTreeWidget)
        tree.update_containers(containers)

        # Select first container if none active
        if not self._active_container and containers:
            first_running = next((c for c in containers if c.is_running), containers[0])
            self._switch_active_container(first_running)

    async def _refresh_disk_usage(self) -> None:
        """Fetch Docker disk usage and update reclaimable statistics."""
        try:
            df_data = await self.api_client.get_disk_usage()
            reclaimable_bytes = 0

            # Images
            for img in df_data.get("Images", []):
                if img.get("SharedSize", 0) == 0:
                    reclaimable_bytes += img.get("Size", 0) // 4  # Estimated dangling

            # Build Cache
            for bc in df_data.get("BuildCache", []):
                if bc.get("Reclaimable", False):
                    reclaimable_bytes += bc.get("Size", 0)

            # Volumes
            for vol in df_data.get("Volumes", []):
                usage = vol.get("UsageData", {})
                if usage.get("RefCount", 0) == 0:
                    reclaimable_bytes += usage.get("Size", 0)

            if reclaimable_bytes > 0:
                header = self.query_one(HeaderBar)
                header.reclaimable_space = format_bytes(reclaimable_bytes)
        except Exception:
            pass

    async def _periodic_inventory_refresh(self) -> None:
        """Poll container list periodically to reflect status transitions."""
        while True:
            await asyncio.sleep(4.0)
            try:
                await self._refresh_containers()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    @on(ContainerTreeWidget.ContainerHighlighted)
    def _on_container_highlighted(self, event: ContainerTreeWidget.ContainerHighlighted) -> None:
        self._switch_active_container(event.container)

    @on(ContainerTreeWidget.ContainerSelected)
    def _on_container_selected(self, event: ContainerTreeWidget.ContainerSelected) -> None:
        self._switch_active_container(event.container)

    def _switch_active_container(self, container: ContainerModel) -> None:
        """Cancel existing streams and connect to selected container telemetry."""
        if self._active_container and self._active_container.id == container.id:
            return

        self._active_container = container
        self._stats_calc = ContainerStatsCalculator()

        spark_panel = self.query_one(SparklinePanel)
        spark_panel.set_container(container)

        log_widget = self.query_one(LogTailWidget)
        log_widget.clear()

        # Cancel active streams
        if self._stats_task and not self._stats_task.done():
            self._stats_task.cancel()
        if self._logs_task and not self._logs_task.done():
            self._logs_task.cancel()

        # Start new stream tasks if running
        if container.is_running:
            self._stats_task = asyncio.create_task(self._stream_stats_loop(container.id))
            self._logs_task = asyncio.create_task(self._stream_logs_loop(container.id))

    async def _stream_stats_loop(self, container_id: str) -> None:
        """Stream real-time stats and pipe to SparklinePanel."""
        spark_panel = self.query_one(SparklinePanel)
        try:
            async for raw_stat in self.api_client.stream_stats(container_id):
                snapshot = self._stats_calc.calculate(raw_stat)
                spark_panel.update_stats(snapshot)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _stream_logs_loop(self, container_id: str) -> None:
        """Stream demultiplexed logs and pipe to LogTailWidget."""
        log_widget = self.query_one(LogTailWidget)
        try:
            async for stream_id, line in self.api_client.stream_logs(
                container_id, tail=100, follow=True
            ):
                log_widget.add_log_line(stream_id, line)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    # Action Handlers
    async def action_restart_container(self) -> None:
        if not self._active_container:
            return
        name = self._active_container.primary_name
        self.notify(f"Restarting container {name}...", title="Docker Action")
        try:
            await self.api_client.restart_container(self._active_container.id)
            self.notify(
                f"Container {name} restarted successfully.", title="Success", severity="information"
            )
            await self._refresh_containers()
        except Exception as err:
            self.notify(f"Failed to restart {name}: {err}", title="Error", severity="error")

    async def action_stop_container(self) -> None:
        if not self._active_container:
            return
        name = self._active_container.primary_name
        self.notify(f"Stopping container {name}...", title="Docker Action")
        try:
            await self.api_client.stop_container(self._active_container.id)
            self.notify(f"Container {name} stopped.", title="Success", severity="information")
            await self._refresh_containers()
        except Exception as err:
            self.notify(f"Failed to stop {name}: {err}", title="Error", severity="error")

    async def action_restart_project(self) -> None:
        """Restart all containers in the active Compose project."""
        if not self._active_container or not self._active_container.compose_project:
            self.notify(
                "Selected container is not part of a Docker Compose project.",
                title="No Compose Project",
                severity="warning",
            )
            return
        project = self._active_container.compose_project
        self.notify(f"Restarting Compose stack '{project}'...", title="Compose Action")
        try:
            restarted_count = await self.api_client.restart_compose_project(project)
            self.notify(
                f"Restarted {restarted_count} container(s) in '{project}'.",
                title="Stack Restarted",
                severity="information",
            )
            await self._refresh_containers()
        except Exception as err:
            self.notify(f"Failed to restart stack: {err}", title="Error", severity="error")

    async def action_stop_project(self) -> None:
        """Stop all containers in the active Compose project."""
        if not self._active_container or not self._active_container.compose_project:
            self.notify(
                "Selected container is not part of a Docker Compose project.",
                title="No Compose Project",
                severity="warning",
            )
            return
        project = self._active_container.compose_project
        self.notify(f"Stopping Compose stack '{project}'...", title="Compose Action")
        try:
            stopped_count = await self.api_client.stop_compose_project(project)
            self.notify(
                f"Stopped {stopped_count} container(s) in '{project}'.",
                title="Stack Stopped",
                severity="information",
            )
            await self._refresh_containers()
        except Exception as err:
            self.notify(f"Failed to stop stack: {err}", title="Error", severity="error")

    def action_open_browser(self) -> None:
        """Open web service in default browser."""
        if not self._active_container:
            return
        url = self._active_container.web_url
        if not url:
            self.notify(
                "No public web port found for this container.",
                title="Web Browser",
                severity="warning",
            )
            return
        try:
            webbrowser.open(url)
            self.notify(
                f"Opened {url} in browser.", title="Browser Launched", severity="information"
            )
        except Exception as err:
            self.notify(f"Failed to open browser: {err}", title="Error", severity="error")

    def action_copy_clipboard(self) -> None:
        """Copy connection string or docker exec command to system clipboard."""
        if not self._active_container:
            return
        conn_str = self._active_container.connection_info
        success = copy_to_clipboard(conn_str)
        if success:
            self.notify(f"Copied: {conn_str}", title="Clipboard", severity="information")
        else:
            self.notify(
                f"Connection URI: {conn_str}", title="URI (Copy manually)", severity="warning"
            )

    async def action_pause_container(self) -> None:
        if not self._active_container:
            return
        cont = self._active_container
        name = cont.primary_name
        try:
            if cont.is_paused:
                self.notify(f"Unpausing container {name}...", title="Docker Action")
                await self.api_client.unpause_container(cont.id)
                self.notify(f"Container {name} resumed.", title="Success")
            else:
                self.notify(f"Pausing container {name}...", title="Docker Action")
                await self.api_client.pause_container(cont.id)
                self.notify(f"Container {name} paused.", title="Success")
            await self._refresh_containers()
        except Exception as err:
            self.notify(f"Failed to toggle pause on {name}: {err}", title="Error", severity="error")

    async def action_remove_container(self) -> None:
        if not self._active_container:
            return
        cont = self._active_container
        name = cont.primary_name
        if cont.is_running:
            self.notify(
                "Cannot remove running container. Stop it first or use force.",
                title="Action Blocked",
                severity="warning",
            )
            return
        try:
            await self.api_client.remove_container(cont.id)
            self.notify(f"Container {name} removed.", title="Success")
            self._active_container = None
            await self._refresh_containers()
        except Exception as err:
            self.notify(f"Failed to remove {name}: {err}", title="Error", severity="error")

    async def action_inspect_container(self) -> None:
        if not self._active_container:
            return
        try:
            inspect_data = await self.api_client.inspect_container(self._active_container.id)
            self.push_screen(DetailModal(inspect_data))
        except Exception as err:
            self.notify(f"Failed to inspect container: {err}", title="Error", severity="error")

    def action_exec_shell(self) -> None:
        if not self._active_container:
            return
        self.push_screen(ShellModal(self.api_client, self._active_container))

    def action_search(self) -> None:
        tree = self.query_one(ContainerTreeWidget)
        tree.focus_search()

    def action_toggle_scroll(self) -> None:
        log_widget = self.query_one(LogTailWidget)
        is_active = log_widget.toggle_auto_scroll()
        status_str = "resumed" if is_active else "paused"
        self.notify(f"Log autoscroll {status_str}.", timeout=2)

    def action_toggle_timestamps(self) -> None:
        log_widget = self.query_one(LogTailWidget)
        is_on = log_widget.toggle_timestamps()
        state_str = "enabled" if is_on else "disabled"
        self.notify(f"Log timestamps {state_str}.", timeout=2)

    def action_cycle_log_level(self) -> None:
        log_widget = self.query_one(LogTailWidget)
        current_filter = log_widget.cycle_severity_filter()
        self.notify(f"Log filter: {current_filter}", timeout=2)

    def action_export_logs(self) -> None:
        if not self._active_container:
            return
        log_widget = self.query_one(LogTailWidget)
        file_path, count = log_widget.export_logs_to_file(self._active_container.primary_name)
        self.notify(
            f"Saved {count} lines to {file_path.name}",
            title="Logs Exported",
            severity="information",
            timeout=4,
        )

    def action_clear_logs(self) -> None:
        log_widget = self.query_one(LogTailWidget)
        log_widget.clear()
        self.notify("Log display cleared.", timeout=2)

    def action_open_images(self) -> None:
        self.push_screen(ImagesModal(self.api_client))

    def action_open_volumes(self) -> None:
        self.push_screen(VolumesModal(self.api_client))

    def action_switch_theme(self) -> None:
        self.push_screen(ThemeModal(self._apply_theme))

    def _apply_theme(self, palette: ThemePalette) -> None:
        """Apply a new color theme at runtime."""
        self.active_palette = palette
        self.screen.styles.background = palette.bg_main
        self.screen.styles.color = palette.text_main
        self.notify(f"Theme switched to {palette.display_name}", title="Theme Applied")

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def action_prune_containers(self) -> None:
        async def on_prune_close(confirmed: bool | None) -> None:
            if confirmed:
                await self._refresh_containers()
                await self._refresh_disk_usage()

        self.push_screen(PruneModal(self.api_client), on_prune_close)
