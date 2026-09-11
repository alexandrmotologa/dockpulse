"""Live telemetry dashboard panel rendering CPU and memory sparklines and I/O metrics."""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from dockpulse.core.container import ContainerModel
from dockpulse.core.sparkline_buffer import SparklineBuffer
from dockpulse.core.stats_streamer import ContainerStatsSnapshot


class SparklinePanel(Widget):
    """Panel rendering live rolling resource sparklines and telemetry."""

    DEFAULT_CSS = """
    SparklinePanel {
        height: 14;
        background: #0b1120;
        border-bottom: solid #1e293b;
        padding: 0 1;
    }
    #telemetry-display {
        height: 100%;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_container: ContainerModel | None = None
        self._cpu_buffer = SparklineBuffer(capacity=40)
        self._mem_buffer = SparklineBuffer(capacity=40)
        self._latest_stats: ContainerStatsSnapshot | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="telemetry-display")

    def set_container(self, container: ContainerModel | None) -> None:
        """Update active container metadata."""
        if container is None:
            self._current_container = None
            self._latest_stats = None
            self._cpu_buffer.clear()
            self._mem_buffer.clear()
            self._render_view()
            return

        if self._current_container is None or self._current_container.id != container.id:
            self._current_container = container
            self._latest_stats = None
            self._cpu_buffer.clear()
            self._mem_buffer.clear()

        self._render_view()

    def update_stats(self, stats: ContainerStatsSnapshot) -> None:
        """Update rolling buffers and re-render metrics."""
        self._latest_stats = stats
        self._cpu_buffer.push(stats.cpu_percent)
        self._mem_buffer.push(stats.memory_percent)
        self._render_view()

    def _render_view(self) -> None:
        static = self.query_one("#telemetry-display", Static)

        if not self._current_container:
            static.update(
                Panel(
                    Text(
                        "Select a container from the tree to view live metrics.", style="dim italic"
                    ),
                    title="Container Telemetry",
                    border_style="#334155",
                )
            )
            return

        cont = self._current_container
        title_text = f"{cont.primary_name} ({cont.short_id})"

        # Header info
        info_text = Text()
        info_text.append(f"Image: {cont.image}  ", style="dim")
        info_text.append(f"Status: {cont.status}  ", style="bold cyan")
        if cont.ports_summary and cont.ports_summary != "-":
            info_text.append(f"Ports: {cont.ports_summary}", style="dim yellow")

        # Sparklines
        cpu_spark = self._cpu_buffer.render(width=32, max_scale=100.0)
        mem_spark = self._mem_buffer.render(width=32, max_scale=100.0)

        cpu_val = self._latest_stats.cpu_percent if self._latest_stats else 0.0
        cpu_avg = self._cpu_buffer.avg_val
        cpu_max = self._cpu_buffer.max_val

        mem_display = (
            self._latest_stats.memory_display if self._latest_stats else "0 B / 0 B (0.0%)"
        )
        net_display = (
            self._latest_stats.network_display if self._latest_stats else "▼ 0 B/s  ▲ 0 B/s"
        )
        io_display = self._latest_stats.block_io_display if self._latest_stats else "R: 0 B  W: 0 B"

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold white", width=12)
        table.add_column(width=34)
        table.add_column()

        # CPU row
        cpu_metrics = f"Cur: [bold cyan]{cpu_val:5.1f}%[/]  Avg: [dim]{cpu_avg:5.1f}%[/]  Max: [dim red]{cpu_max:5.1f}%[/]"
        table.add_row("CPU Usage", f"[bold green]{cpu_spark}[/]", cpu_metrics)

        # Memory row
        mem_metrics = f"{mem_display}"
        table.add_row("Memory RSS", f"[bold yellow]{mem_spark}[/]", mem_metrics)

        # Network & Disk row
        table.add_row("Network I/O", net_display, f"Disk I/O: {io_display}")

        content = Text()
        content.append_text(info_text)
        content.append("\n\n")

        panel = Panel(
            table,
            title=f"⚡ {title_text}",
            subtitle=info_text.plain,
            border_style="#0284c7" if cont.is_running else "#475569",
        )
        static.update(panel)
