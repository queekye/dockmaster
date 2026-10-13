"""Mock-only regression tests for credentials/default project isolation."""

from copy import deepcopy
import json
from unittest.mock import Mock

from typer.testing import CliRunner

from dockmaster.cli import app
from dockmaster.constants import DEFAULT_PROJECT_CONFIG
from dockmaster.managers.base_manager import BaseManager
from dockmaster.managers.config_manager import ConfigManager
from dockmaster.managers.image.push import ImagePusher


def test_help_does_not_connect_to_docker(monkeypatch):
    def forbidden():
        raise AssertionError("CLI help must not connect to Docker")
    monkeypatch.setattr("docker.from_env", forbidden)
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "Docker" in result.output


def test_projects_do_not_share_default_nested_state(monkeypatch, tmp_path):
    monkeypatch.setattr(BaseManager, "__init__", lambda self: None)
    baseline = deepcopy(DEFAULT_PROJECT_CONFIG)
    first = ConfigManager("first", str(tmp_path / "first")).create_default_config()
    second = ConfigManager("second", str(tmp_path / "second")).create_default_config()
    first["image"]["registry"]["username"] = "fixture-user"
    first["container"]["cleanup"]["paths"].append("/fixture")
    assert second["project"]["name"] == "second"
    assert first["project"]["name"] == "first"
    assert second["image"]["registry"]["username"] == ""
    assert "/fixture" not in second["container"]["cleanup"]["paths"]
    assert DEFAULT_PROJECT_CONFIG == baseline


def test_legacy_password_is_not_written_to_config(monkeypatch, tmp_path):
    monkeypatch.setattr(BaseManager, "__init__", lambda self: None)
    manager = ConfigManager("fixture", str(tmp_path))
    manager.create_default_config()
    manager.config["image"]["registry"]["password"] = "not-a-real-secret-fixture"
    manager.save_config()
    written = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "not-a-real-secret-fixture" not in written
    assert json.loads(written)["image"]["registry"]["password"] == ""


def test_environment_credentials_reach_mock_login_without_files(monkeypatch):
    client = Mock()
    monkeypatch.setenv("DOCKER_PASSWORD_FIXTURE", "fixture-only-not-real")
    pusher = ImagePusher(client, "sample:latest")
    password = pusher._get_password_from_env("fixture")
    assert pusher._do_login("registry.invalid", "fixture", password)
    client.login.assert_called_once_with(
        registry="registry.invalid", username="fixture", password="fixture-only-not-real",
    )
    client.images.push.assert_not_called()


def test_cli_does_not_use_legacy_plaintext_password(monkeypatch):
    import dockmaster.cli as cli
    manager = Mock()
    manager.config = deepcopy(DEFAULT_PROJECT_CONFIG)
    manager.config["image"]["name"] = "fixture"
    manager.config["image"]["registry"]["password"] = "not-a-real-legacy-fixture"
    manager.image_manager.push_image.return_value = True
    monkeypatch.delenv("DOCKER_PASSWORD", raising=False)
    monkeypatch.delenv("DOCKER_PASSWORD_FIXTURE", raising=False)
    monkeypatch.setattr(cli, "get_project_manager", lambda: manager)
    monkeypatch.setattr(cli.typer, "prompt", lambda *args, **kwargs: "")
    cli.push_image.__wrapped__(
        registry="registry.invalid", username="fixture", password=None,
        tag="latest", prefix="fixture", force=True, use_timestamp=False,
    )
    manager.image_manager.push_image.assert_called_once_with(
        "registry.invalid", "fixture", None, prefix="fixture", use_timestamp_tag=False,
    )
