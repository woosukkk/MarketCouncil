from unittest.mock import patch

from app.local_services import ensure_local_services


def test_ready_service_skips_docker_start() -> None:
    with (
        patch("app.local_services._service_ready", return_value=True),
        patch("app.local_services._docker_ready") as docker_ready,
        patch("app.local_services._start_docker_desktop") as start_docker,
    ):
        ensure_local_services()

    docker_ready.assert_not_called()
    start_docker.assert_not_called()
