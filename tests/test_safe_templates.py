"""Safety tests use local configuration and fake processes, never Docker."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GPU = ROOT / "templates" / "gpu"


def bash_path(path):
    value = Path(path).resolve().as_posix()
    if os.name == "nt" and len(value) > 2 and value[1] == ":":
        return "/" + value[0].lower() + value[2:]
    return value


def shell(script, env=None, args=()):
    executable = os.environ.get("BASH_EXE") or shutil.which("bash")
    if not executable:
        pytest.skip("Bash is required for the runtime template checks")
    return subprocess.run(
        [executable, "--noprofile", "--norc", bash_path(script), *args],
        env={**os.environ, "PATH": "/usr/bin:/bin", **(env or {})},
        text=True, capture_output=True, timeout=10,
    )


def test_default_network_and_no_secret_image_identity():
    compose = yaml.safe_load((GPU / "docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["modern-train"]
    assert service["ports"] == ["127.0.0.1:21888:8888"]
    assert service["environment"]["ENABLE_SSH"] == "0"
    assert service["environment"]["ENABLE_MLFLOW"] == "0"
    dockerfile = (GPU / "Dockerfile").read_text(encoding="utf-8")
    assert "ssh-keygen" not in dockerfile
    assert "rm -f /etc/ssh/ssh_host_*" in dockerfile
    assert "id_rsa" not in dockerfile
    ssh_config = (GPU / "sshd_config").read_text(encoding="utf-8")
    assert "PermitRootLogin no" in ssh_config
    assert "PasswordAuthentication no" in ssh_config
    assert "AuthenticationMethods publickey" in ssh_config


def test_optional_keys_are_readonly_and_missing_paths_not_created():
    config = yaml.safe_load((GPU / "docker-compose.ssh.yml").read_text(encoding="utf-8"))
    service = config["services"]["modern-train"]
    assert service["ports"] == ["127.0.0.1:21022:22"]
    mount = service["volumes"][0]
    assert mount["read_only"] is True
    assert mount["bind"]["create_host_path"] is False
    assert ":?" in mount["source"]


def test_preflight_does_not_start_services():
    result = shell(GPU / "start_service.sh", {"ENABLE_SSH": "0", "ENABLE_MLFLOW": "0"}, ["--check"])
    assert result.returncode == 0, result.stderr
    assert "Configuration OK" in result.stdout


@pytest.mark.parametrize("settings", [
    {"ENABLE_SSH": "yes"}, {"ENABLE_MLFLOW": "invalid"},
    {"ENABLE_SSH": "1", "SSH_AUTHORIZED_KEYS_FILE": "/does-not-exist/authorized_keys"},
])
def test_bad_config_fails_before_service_launch(settings):
    result = shell(GPU / "start_service.sh", settings, ["--check"])
    assert result.returncode == 2
    assert result.stderr


def test_explicit_public_key_input(tmp_path):
    keys = tmp_path / "authorized_keys"
    keys.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixtureOnlyNotARealKey test\n")
    result = shell(GPU / "start_service.sh", {
        "ENABLE_SSH": "1", "ENABLE_MLFLOW": "0", "SSH_AUTHORIZED_KEYS_FILE": bash_path(keys),
    }, ["--check"])
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mlflow,exit_code", [("0", 0), ("0", 42), ("1", 42)])
def test_runtime_auth_local_mlflow_and_failure_exit(tmp_path, mlflow, exit_code):
    """Exercise actual shell control flow against fake runuser/services."""
    stubs = tmp_path / "bin"
    stubs.mkdir()
    log = tmp_path / "commands.txt"
    fake_runuser = stubs / "runuser"
    fake_runuser.write_text('''#!/usr/bin/env bash
set -eu
[[ "$1" == -u && "$2" == developer && "$3" == -- ]]
shift 3
printf '%s\n' "$*" >> "$COMMAND_LOG"
case "$1" in
  mkdir) exit 0 ;;
  mlflow) sleep 5 ;;
  jupyter) sleep 0.15; exit "$JUPYTER_EXIT" ;;
  *) exit 99 ;;
esac
''', encoding="utf-8", newline="\n")
    fake_runuser.chmod(0o755)
    result = shell(GPU / "start_service.sh", {
        "PATH": bash_path(stubs) + ":/usr/bin:/bin",
        "COMMAND_LOG": bash_path(log), "JUPYTER_EXIT": str(exit_code),
        "ENABLE_SSH": "0", "ENABLE_MLFLOW": mlflow,
        "WORKSPACE_DIR": bash_path(tmp_path / "workspace"),
    })
    assert result.returncode == exit_code, result.stderr
    commands = log.read_text(encoding="utf-8")
    assert "jupyter lab" in commands
    assert "--ServerApp.ip=0.0.0.0" in commands
    assert "token=" not in commands
    assert "--allow-root" not in commands
    if mlflow == "1":
        assert "mlflow server --host 127.0.0.1" in commands
        assert "sqlite:///" in commands
    else:
        assert "mlflow server" not in commands


def test_example_has_no_personal_directory_or_jobs():
    config = json.loads((GPU / "config.json").read_text(encoding="utf-8"))
    assert config["project"]["directory"] == "."
    assert config["image"]["registry"]["password"] == ""
    assert config["image"]["registry"]["username"] == ""
    assert config["schedule"] == {}
    assert config["container"]["backup"] == {"cleanup": False, "auto_push": False}


def test_manifest_covers_original_payload_and_delivered_hashes():
    import hashlib
    manifest = json.loads((GPU / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    originals = [row for row in manifest["files"] if row["source_sha256"]]
    assert len(originals) == 6
    assert {Path(row["source_path"]).name for row in originals} == {
        "Dockerfile", "start_service.sh", "docker-compose.yml", "config.json", "requirements.txt", ".dockerignore"
    }
    for row in manifest["files"]:
        path = ROOT / row["destination_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["delivered_sha256"]
