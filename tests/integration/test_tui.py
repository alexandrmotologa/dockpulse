"""Headless integration tests for DockPulseHUD."""

import pytest

from dockpulse.config import DockerConfig
from dockpulse.tui.app import DockPulseHUD
from dockpulse.tui.widgets.container_tree import ContainerTreeWidget
from dockpulse.tui.widgets.header_bar import HeaderBar
from dockpulse.tui.widgets.log_tail import LogTailWidget
from dockpulse.tui.widgets.sparkline_panel import SparklinePanel


@pytest.mark.asyncio
async def test_tui_app_lifecycle() -> None:
    config = DockerConfig(socket_path="mock://docker_engine", socket_type="mock", is_demo=True)
    app = DockPulseHUD(config=config)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Check widget composition
        header = pilot.app.query_one(HeaderBar)
        assert header is not None
        assert "[DEMO MODE]" in header.socket_label

        tree = pilot.app.query_one(ContainerTreeWidget)
        assert tree is not None

        panel = pilot.app.query_one(SparklinePanel)
        assert panel is not None

        logs = pilot.app.query_one(LogTailWidget)
        assert logs is not None

        # Verify log controls (pause, clear, toggle timestamps, cycle severity)
        await pilot.press("space")
        await pilot.pause()

        await pilot.press("t")
        await pilot.pause()

        await pilot.press("l")
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        # Test Stack actions (Shift+R, Shift+S)
        await pilot.press("R")
        await pilot.pause()

        await pilot.press("S")
        await pilot.pause()

        # Test Modals (Images 'i', Volumes 'v', Themes 'T', Help '?')
        await pilot.press("i")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("v")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("T")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("question_mark")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        # Exit cleanly
        await pilot.press("q")
