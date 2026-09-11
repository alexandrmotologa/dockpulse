"""Tests for Docker Compose project grouping logic."""

from dockpulse.core.container import ContainerModel, group_containers_by_compose


def test_group_containers_by_compose() -> None:
    c1 = ContainerModel.model_validate(
        {
            "Id": "c11111111111",
            "Names": ["/projA_web_1"],
            "State": "running",
            "Labels": {
                "com.docker.compose.project": "project-alpha",
                "com.docker.compose.service": "web",
                "com.docker.compose.container-number": "1",
            },
        }
    )
    c2 = ContainerModel.model_validate(
        {
            "Id": "c22222222222",
            "Names": ["/projA_db_1"],
            "State": "running",
            "Labels": {
                "com.docker.compose.project": "project-alpha",
                "com.docker.compose.service": "db",
                "com.docker.compose.container-number": "1",
            },
        }
    )
    c3 = ContainerModel.model_validate(
        {
            "Id": "c33333333333",
            "Names": ["/standalone_redis"],
            "State": "running",
            "Labels": {},
        }
    )

    projects, standalone = group_containers_by_compose([c1, c2, c3])

    assert len(projects) == 1
    assert projects[0].name == "project-alpha"
    assert projects[0].total_count == 2
    assert projects[0].running_count == 2
    assert projects[0].is_all_running is True
    assert len(standalone) == 1
    assert standalone[0].primary_name == "standalone_redis"
