"""Container and Docker Compose data models."""

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field


class PortMapping(BaseModel):
    """Port publication mapping."""

    model_config = ConfigDict(populate_by_name=True)

    ip: str | None = Field(default=None, alias="IP")
    private_port: int = Field(alias="PrivatePort")
    public_port: int | None = Field(default=None, alias="PublicPort")
    port_type: str = Field(default="tcp", alias="Type")

    def __str__(self) -> str:
        if self.public_port:
            return f"{self.public_port}:{self.private_port}/{self.port_type}"
        return f"{self.private_port}/{self.port_type}"


class ContainerModel(BaseModel):
    """Normalized Docker container model."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(alias="Id")
    names: list[str] = Field(default_factory=list, alias="Names")
    image: str = Field(default="", alias="Image")
    image_id: str | None = Field(default=None, alias="ImageID")
    command: str | None = Field(default=None, alias="Command")
    created: int = Field(default=0, alias="Created")
    state: str = Field(default="unknown", alias="State")
    status: str = Field(default="", alias="Status")
    ports: list[PortMapping] = Field(default_factory=list, alias="Ports")
    labels: dict[str, str] = Field(default_factory=dict, alias="Labels")

    @property
    def short_id(self) -> str:
        """12-character short container ID."""
        return self.id[:12] if len(self.id) >= 12 else self.id

    @property
    def primary_name(self) -> str:
        """First container name without leading slash."""
        if self.names:
            return self.names[0].lstrip("/")
        return self.short_id

    @property
    def compose_project(self) -> str | None:
        """Docker Compose project name if managed by Compose."""
        return self.labels.get("com.docker.compose.project")

    @property
    def compose_service(self) -> str | None:
        """Docker Compose service name."""
        return self.labels.get("com.docker.compose.service")

    @property
    def compose_container_number(self) -> int:
        """Compose replica number."""
        num_str = self.labels.get("com.docker.compose.container-number", "1")
        try:
            return int(num_str)
        except ValueError:
            return 1

    @property
    def is_running(self) -> bool:
        return self.state.lower() == "running"

    @property
    def is_paused(self) -> bool:
        return self.state.lower() == "paused"

    @property
    def is_restarting(self) -> bool:
        return self.state.lower() == "restarting"

    @property
    def is_exited(self) -> bool:
        return self.state.lower() in ("exited", "dead")

    @property
    def health_status(self) -> str:
        """Extract health status (healthy, unhealthy, starting, none)."""
        status_lower = self.status.lower()
        if "(healthy)" in status_lower:
            return "healthy"
        if "(unhealthy)" in status_lower:
            return "unhealthy"
        if "(health: starting)" in status_lower:
            return "starting"
        return "none"

    @property
    def is_oom_killed(self) -> bool:
        """Check if container died due to Out of Memory (exit code 137 or OOM marker)."""
        status_lower = self.status.lower()
        return "137" in status_lower or "oom" in status_lower

    @property
    def is_crash_loop(self) -> bool:
        """Check if container is flapping or restarting repeatedly."""
        return self.is_restarting or "restarting" in self.status.lower()

    @property
    def status_badge(self) -> str:
        """Visual status emoji or badge with watchdog anomalies."""
        if self.is_oom_killed:
            return "💀 oom_killed"
        if self.is_crash_loop:
            return "⚠️ crash_loop"
        if self.is_running:
            if self.health_status == "unhealthy":
                return "🔴 unhealthy"
            if self.health_status == "starting":
                return "🟡 starting"
            return "🟢 running"
        if self.is_paused:
            return "⏸️ paused"
        if self.is_restarting:
            return "🔄 restarting"
        return "🔴 exited"

    @property
    def web_url(self) -> str | None:
        """HTTP or HTTPS web URL for exposed public services."""
        for p in self.ports:
            if p.public_port:
                if p.public_port == 443 or p.private_port == 443:
                    return f"https://localhost:{p.public_port}"
                if p.public_port in (80, 8080, 8000, 3000, 5173, 8081, 9090, 16686):
                    return f"http://localhost:{p.public_port}"

        # Fallback to first public port
        for p in self.ports:
            if p.public_port:
                return f"http://localhost:{p.public_port}"
        return None

    @property
    def connection_info(self) -> str:
        """Formatted connection URI or shell exec command."""
        img_lower = self.image.lower()
        first_port = next((p.public_port for p in self.ports if p.public_port), None)
        if "postgres" in img_lower and first_port:
            return f"postgresql://postgres:postgres@localhost:{first_port}/dbname"
        if "redis" in img_lower and first_port:
            return f"redis://localhost:{first_port}"
        if "mysql" in img_lower and first_port:
            return f"mysql://root:password@127.0.0.1:{first_port}/dbname"
        if "mongo" in img_lower and first_port:
            return f"mongodb://localhost:{first_port}"
        if first_port:
            return f"http://localhost:{first_port}"
        return f"docker exec -it {self.primary_name} sh"

    @property
    def ports_summary(self) -> str:
        """Formatted string of published ports."""
        active_ports = [str(p) for p in self.ports if p.public_port]
        if not active_ports:
            return "-"
        return ", ".join(active_ports[:3]) + (
            f" (+{len(active_ports) - 3})" if len(active_ports) > 3 else ""
        )


class ComposeProject(BaseModel):
    """Collection of containers belonging to a Docker Compose project."""

    name: str
    containers: list[ContainerModel] = Field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.containers)

    @property
    def running_count(self) -> int:
        return sum(1 for c in self.containers if c.is_running)

    @property
    def status_summary(self) -> str:
        return f"{self.running_count}/{self.total_count} running"

    @property
    def is_all_running(self) -> bool:
        return self.total_count > 0 and self.running_count == self.total_count


def group_containers_by_compose(
    containers: list[ContainerModel],
) -> tuple[list[ComposeProject], list[ContainerModel]]:
    """Group containers into Compose projects and standalone containers.

    Returns:
        (compose_projects, standalone_containers)
    """
    project_map: dict[str, list[ContainerModel]] = defaultdict(list)
    standalone: list[ContainerModel] = []

    for container in containers:
        project_name = container.compose_project
        if project_name:
            project_map[project_name].append(container)
        else:
            standalone.append(container)

    # Sort projects by name and containers within project by service name
    projects: list[ComposeProject] = []
    for name in sorted(project_map.keys()):
        sorted_conts = sorted(
            project_map[name],
            key=lambda c: (c.compose_service or c.primary_name, c.compose_container_number),
        )
        projects.append(ComposeProject(name=name, containers=sorted_conts))

    standalone_sorted = sorted(standalone, key=lambda c: c.primary_name)
    return projects, standalone_sorted
