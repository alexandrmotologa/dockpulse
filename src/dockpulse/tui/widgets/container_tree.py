"""Hierarchical tree widget displaying containers grouped by Compose project."""

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Tree
from textual.widgets.tree import TreeNode

from dockpulse.core.container import (
    ContainerModel,
    group_containers_by_compose,
)


class ContainerTreeWidget(Widget):
    """Navigable tree grouping containers by Docker Compose project."""

    DEFAULT_CSS = """
    ContainerTreeWidget {
        width: 38;
        height: 100%;
        background: #090d16;
        border-right: solid #1e293b;
        layout: vertical;
    }
    #search-input {
        height: 3;
        margin: 0 1;
        background: #0f172a;
        border: tall #334155;
        color: #f1f5f9;
    }
    #search-input:focus {
        border: tall #38bdf8;
    }
    #tree-view {
        height: 1fr;
        background: #090d16;
        scrollbar-gutter: stable;
        padding: 0 1;
    }
    #tree-view > .tree--cursor {
        background: #1e293b;
        color: #38bdf8;
        text-style: bold;
    }
    """

    class ContainerSelected(Message):
        """Emitted when a container is selected (Enter pressed)."""

        def __init__(self, container: ContainerModel) -> None:
            super().__init__()
            self.container = container

    class ContainerHighlighted(Message):
        """Emitted when cursor moves over a container node."""

        def __init__(self, container: ContainerModel) -> None:
            super().__init__()
            self.container = container

    def __init__(self) -> None:
        super().__init__()
        self._all_containers: list[ContainerModel] = []
        self._filter_query: str = ""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="🔍 Search (/ to focus)...", id="search-input")
        tree: Tree[ContainerModel | None] = Tree("Containers", id="tree-view")
        tree.show_root = False
        yield tree

    def update_containers(self, containers: list[ContainerModel]) -> None:
        """Update the full container list and refresh the tree view."""
        self._all_containers = containers
        self._refresh_tree()

    def set_filter(self, query: str) -> None:
        """Apply a filter query."""
        self._filter_query = query.strip().lower()
        search_input = self.query_one("#search-input", Input)
        if search_input.value != query:
            search_input.value = query
        self._refresh_tree()

    @on(Input.Changed, "#search-input")
    def _on_search_changed(self, event: Input.Changed) -> None:
        self._filter_query = event.value.strip().lower()
        self._refresh_tree()

    @on(Input.Submitted, "#search-input")
    def _on_search_submitted(self) -> None:
        tree = self.query_one("#tree-view", Tree)
        tree.focus()

    def focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def focus_tree(self) -> None:
        """Focus the tree view."""
        self.query_one("#tree-view", Tree).focus()

    def _refresh_tree(self) -> None:
        tree: Tree[ContainerModel | None] = self.query_one("#tree-view", Tree)
        tree.clear()

        filtered = self._all_containers
        if self._filter_query:
            filtered = [
                c
                for c in self._all_containers
                if self._filter_query in c.primary_name.lower()
                or self._filter_query in c.image.lower()
                or (c.compose_project and self._filter_query in c.compose_project.lower())
                or (c.compose_service and self._filter_query in c.compose_service.lower())
            ]

        projects, standalone = group_containers_by_compose(filtered)

        # 1. Compose projects
        for proj in projects:
            summary_color = "green" if proj.is_all_running else "yellow"
            label = Text()
            label.append("📁 ", style="bold blue")
            label.append(proj.name, style="bold white")
            label.append(f" [{proj.status_summary}]", style=f"dim {summary_color}")

            proj_node = tree.root.add(label, data=None, expand=True)
            for cont in proj.containers:
                self._add_container_leaf(proj_node, cont)

        # 2. Standalone containers
        if standalone:
            standalone_node = tree.root.add(
                Text("📦 Standalone", style="bold magenta"), data=None, expand=True
            )
            for cont in standalone:
                self._add_container_leaf(standalone_node, cont)

    def _add_container_leaf(
        self, parent: TreeNode[ContainerModel | None], cont: ContainerModel
    ) -> None:
        label = Text()
        if cont.is_running:
            label.append("🟢 " if cont.health_status != "unhealthy" else "🔴 ")
        elif cont.is_paused:
            label.append("⏸️ ")
        else:
            label.append("🔴 ")

        name = cont.compose_service or cont.primary_name
        label.append(name, style="bold cyan" if cont.is_running else "dim white")

        if cont.ports_summary and cont.ports_summary != "-":
            label.append(f"  {cont.ports_summary}", style="dim")

        parent.add_leaf(label, data=cont)

    @on(Tree.NodeHighlighted, "#tree-view")
    def _on_highlighted(self, event: Tree.NodeHighlighted[ContainerModel | None]) -> None:
        if event.node and event.node.data is not None:
            self.post_message(self.ContainerHighlighted(event.node.data))

    @on(Tree.NodeSelected, "#tree-view")
    def _on_selected(self, event: Tree.NodeSelected[ContainerModel | None]) -> None:
        if event.node and event.node.data is not None:
            self.post_message(self.ContainerSelected(event.node.data))
        elif event.node:
            event.node.toggle()
