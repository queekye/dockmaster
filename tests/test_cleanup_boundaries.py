"""No real Docker; guard protected paths and shell argument boundaries."""

from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import Mock

import docker
import pytest

from dockmaster.cleanup import cleanup_container_paths, validate_cleanup_path
from dockmaster.managers.container_manager import ContainerManager
from dockmaster.managers.image_manager import ImageManager
from dockmaster.utils import run_command


@pytest.mark.parametrize("path", [
    "/", "/tmp", "/var/cache", "/root/.cache", "/workspace/results", "/datasets/vtqa",
    "/root/.ssh", "/tmp/../workspace", "/tmp/*", "-rf", "relative", "/tmp/x\n/data",
])
def test_unsafe_paths_rejected_before_any_docker_call(path):
    container = Mock()
    with pytest.raises(ValueError):
        cleanup_container_paths(container, ["/tmp/dockmaster", path])
    container.exec_run.assert_not_called()


def test_symlink_escape_refused_without_rm():
    container = Mock()
    container.exec_run.return_value = SimpleNamespace(exit_code=0, output=b"/workspace/data\n")
    with pytest.raises(ValueError):
        cleanup_container_paths(container, ["/tmp/link/data"])
    container.exec_run.assert_called_once_with(["readlink", "-f", "--", "/tmp/link/data"])


def test_cleanup_commands_are_argument_lists_and_failed_rm_not_success():
    container = Mock()
    container.exec_run.side_effect = [
        SimpleNamespace(exit_code=0, output=b"/tmp/dockmaster\n"),
        SimpleNamespace(exit_code=1, output=b"permission denied"),
    ]
    with pytest.raises(RuntimeError):
        cleanup_container_paths(container, ["/tmp/dockmaster"])
    assert container.exec_run.call_args.args[0] == ["rm", "-rf", "--", "/tmp/dockmaster"]


def test_accepted_exact_cache_path():
    container = Mock()
    container.exec_run.side_effect = [
        SimpleNamespace(exit_code=0, output=b"/root/.cache/huggingface\n"),
        SimpleNamespace(exit_code=0, output=b""),
    ]
    assert cleanup_container_paths(container, ["/root/.cache/huggingface"]) == ["/root/.cache/huggingface"]


def test_shell_metacharacters_remain_literal_arguments():
    argument = "a path; echo SHOULDNTRUN & with spaces"
    code, stdout, stderr = run_command([sys.executable, "-c", "import sys;print(sys.argv[1])", argument])
    assert code == 0
    assert stdout.strip() == argument
    with pytest.raises(ValueError):
        run_command([sys.executable, "-V"], shell=True)


def test_compose_path_is_not_shell_interpolated(monkeypatch, tmp_path):
    manager = ContainerManager.__new__(ContainerManager)
    project = tmp_path / "with spaces; literal"
    project.mkdir()
    (project / "docker-compose.yml").write_text("services: {}")
    manager.project_dir = project
    manager.container_name = "fixture"
    manager.docker_client = Mock()
    manager.docker_client.containers.get.side_effect = docker.errors.NotFound("fixture not running")
    monkeypatch.setattr(manager, "_wait_for_container_status", lambda *args: (True, None))
    command = Mock(return_value=(0, "", ""))
    monkeypatch.setattr("dockmaster.managers.container_manager.run_command", command)
    assert manager.start_container()
    command.assert_called_once_with([
        "docker", "compose", "-f", str(project / "docker-compose.yml"), "up", "-d",
    ])


def test_failed_cleanup_stops_mock_backup():
    manager = ImageManager.__new__(ImageManager)
    manager.docker_client = Mock()
    container = manager.docker_client.containers.get.return_value
    container.exec_run.return_value = SimpleNamespace(exit_code=1, output=b"")
    assert manager.create_from_container("fixture", cleanup=True) is False
    container.commit.assert_not_called()
