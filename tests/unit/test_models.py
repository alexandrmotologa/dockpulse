"""Tests for ContainerModel and PortMapping."""

from dockpulse.core.container import ContainerModel, PortMapping


def test_port_mapping_str() -> None:
    port1 = PortMapping(IP="0.0.0.0", PrivatePort=80, PublicPort=8080, Type="tcp")
    assert str(port1) == "8080:80/tcp"

    port2 = PortMapping(PrivatePort=5432, Type="tcp")
    assert str(port2) == "5432/tcp"


def test_container_model_parsing() -> None:
    raw = {
        "Id": "1234567890abcdef1234567890abcdef",
        "Names": ["/my-awesome-service-1"],
        "Image": "my-org/service:v1.0",
        "State": "running",
        "Status": "Up 2 hours (healthy)",
        "Ports": [{"PrivatePort": 8000, "PublicPort": 8000, "Type": "tcp"}],
        "Labels": {
            "com.docker.compose.project": "ecommerce",
            "com.docker.compose.service": "auth-service",
            "com.docker.compose.container-number": "2",
        },
    }
    model = ContainerModel.model_validate(raw)

    assert model.short_id == "1234567890ab"
    assert model.primary_name == "my-awesome-service-1"
    assert model.compose_project == "ecommerce"
    assert model.compose_service == "auth-service"
    assert model.compose_container_number == 2
    assert model.is_running is True
    assert model.health_status == "healthy"
    assert "🟢" in model.status_badge
    assert "8000:8000/tcp" in model.ports_summary


def test_container_model_exited() -> None:
    raw = {
        "Id": "fedcba0987654321",
        "Names": ["/stopped-worker"],
        "Image": "alpine:latest",
        "State": "exited",
        "Status": "Exited (1) 10 minutes ago",
    }
    model = ContainerModel.model_validate(raw)
    assert model.is_running is False
    assert model.is_exited is True
    assert "🔴" in model.status_badge
