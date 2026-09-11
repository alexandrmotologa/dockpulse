"""Terminal HUD themes and styling palettes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    """Color palette definition for DockPulse HUD."""

    name: str
    display_name: str
    bg_main: str
    bg_secondary: str
    bg_panel: str
    border: str
    border_focus: str
    accent: str
    accent_secondary: str
    text_main: str
    text_dim: str

    def generate_css(self) -> str:
        """Generate Textual CSS stylesheet for this theme."""
        return f"""
        Screen {{
            background: {self.bg_main};
            color: {self.text_main};
            layout: vertical;
        }}
        #main-body {{
            height: 1fr;
            layout: horizontal;
        }}
        #content-pane {{
            width: 1fr;
            height: 100%;
            layout: vertical;
        }}
        HeaderBar {{
            height: 3;
            dock: top;
            background: {self.bg_secondary};
            color: {self.text_main};
            border-bottom: solid {self.border};
            padding: 0 1;
            layout: horizontal;
        }}
        #brand-title {{
            width: 22;
            content-align: left middle;
            text-style: bold;
            color: {self.accent};
        }}
        #daemon-info {{
            width: 1fr;
            content-align: left middle;
            color: {self.text_dim};
        }}
        #counts-summary {{
            width: auto;
            content-align: right middle;
        }}
        ContainerTreeWidget {{
            width: 38;
            height: 100%;
            background: {self.bg_secondary};
            border-right: solid {self.border};
            layout: vertical;
        }}
        #search-input {{
            height: 3;
            margin: 0 1;
            background: {self.bg_main};
            border: tall {self.border};
            color: {self.text_main};
        }}
        #search-input:focus {{
            border: tall {self.border_focus};
        }}
        #tree-view {{
            height: 1fr;
            background: {self.bg_secondary};
            scrollbar-gutter: stable;
            padding: 0 1;
        }}
        #tree-view > .tree--cursor {{
            background: {self.bg_panel};
            color: {self.accent};
            text-style: bold;
        }}
        SparklinePanel {{
            height: 15;
            background: {self.bg_panel};
            border-bottom: solid {self.border};
            padding: 0 1;
        }}
        #telemetry-display {{
            height: 100%;
        }}
        LogTailWidget {{
            height: 1fr;
            background: {self.bg_main};
            layout: vertical;
            padding: 0 1;
        }}
        #log-header {{
            height: 1;
            background: {self.bg_secondary};
            color: {self.text_dim};
        }}
        #log-filter-input {{
            height: 3;
            margin: 0 0 1 0;
            background: {self.bg_panel};
            border: tall {self.border};
            color: {self.text_main};
            display: none;
        }}
        #log-filter-input:focus {{
            border: tall {self.border_focus};
        }}
        #rich-log-box {{
            height: 1fr;
            background: {self.bg_main};
            scrollbar-gutter: stable;
            border: solid {self.border};
        }}
        """


THEMES: dict[str, ThemePalette] = {
    "default": ThemePalette(
        name="default",
        display_name="Slate & Cyan (Default)",
        bg_main="#020617",
        bg_secondary="#090d16",
        bg_panel="#0b1120",
        border="#1e293b",
        border_focus="#38bdf8",
        accent="#38bdf8",
        accent_secondary="#10b981",
        text_main="#f8fafc",
        text_dim="#94a3b8",
    ),
    "tokyo_night": ThemePalette(
        name="tokyo_night",
        display_name="Tokyo Night",
        bg_main="#1a1b26",
        bg_secondary="#16161e",
        bg_panel="#24283b",
        border="#414868",
        border_focus="#7dcfff",
        accent="#7dcfff",
        accent_secondary="#bb9af7",
        text_main="#c0caf5",
        text_dim="#787c99",
    ),
    "catppuccin": ThemePalette(
        name="catppuccin",
        display_name="Catppuccin Mocha",
        bg_main="#1e1e2e",
        bg_secondary="#181825",
        bg_panel="#313244",
        border="#45475a",
        border_focus="#cba6f7",
        accent="#cba6f7",
        accent_secondary="#89b4fa",
        text_main="#cdd6f4",
        text_dim="#a6adc8",
    ),
    "dracula": ThemePalette(
        name="dracula",
        display_name="Dracula",
        bg_main="#282a36",
        bg_secondary="#21222c",
        bg_panel="#44475a",
        border="#6272a4",
        border_focus="#bd93f9",
        accent="#bd93f9",
        accent_secondary="#50fa7b",
        text_main="#f8f8f2",
        text_dim="#6272a4",
    ),
    "nord": ThemePalette(
        name="nord",
        display_name="Nord Arctic",
        bg_main="#2e3440",
        bg_secondary="#242933",
        bg_panel="#3b4252",
        border="#4c566a",
        border_focus="#88c0d0",
        accent="#88c0d0",
        accent_secondary="#a3be8c",
        text_main="#eceff4",
        text_dim="#d8dee9",
    ),
}


def get_theme(theme_name: str) -> ThemePalette:
    """Retrieve theme palette by name with fallback to default."""
    return THEMES.get(theme_name.lower().strip(), THEMES["default"])
