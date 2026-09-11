"""Theme selector modal screen."""

from collections.abc import Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from dockpulse.core.theme import THEMES, ThemePalette


class ThemeModal(ModalScreen[None]):
    """Modal dialog for previewing and selecting color themes."""

    DEFAULT_CSS = """
    ThemeModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #theme-box {
        width: 54;
        height: auto;
        background: #0f172a;
        border: thick #38bdf8;
        padding: 1 2;
    }
    #theme-title {
        text-style: bold;
        color: #38bdf8;
        margin-bottom: 1;
    }
    #theme-list {
        height: 8;
        background: #1e293b;
        margin-bottom: 1;
    }
    #theme-buttons {
        height: 3;
        align: right middle;
    }
    #theme-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, on_theme_selected: Callable[[ThemePalette], None]) -> None:
        super().__init__()
        self.on_theme_selected = on_theme_selected
        self._theme_keys = list(THEMES.keys())

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-box"):
            yield Static("🎨 Select HUD Theme", id="theme-title")
            options = [Option(f"{t.display_name}", id=k) for k, t in THEMES.items()]
            yield OptionList(*options, id="theme-list")
            with Horizontal(id="theme-buttons"):
                yield Button("Apply", id="apply-btn", variant="primary")
                yield Button("Cancel (Esc)", id="cancel-btn", variant="default")

    @on(OptionList.OptionSelected, "#theme-list")
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        key = str(event.option_id)
        palette = THEMES.get(key)
        if palette:
            self.on_theme_selected(palette)
            self.dismiss()

    @on(Button.Pressed, "#apply-btn")
    def _on_apply(self) -> None:
        opt_list = self.query_one("#theme-list", OptionList)
        if opt_list.highlighted is not None:
            key = self._theme_keys[opt_list.highlighted]
            palette = THEMES.get(key)
            if palette:
                self.on_theme_selected(palette)
        self.dismiss()

    @on(Button.Pressed, "#cancel-btn")
    def _on_cancel(self) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()
