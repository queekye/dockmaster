#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

enable_ssh=${ENABLE_SSH:-0}
enable_mlflow=${ENABLE_MLFLOW:-0}
keys_file=${SSH_AUTHORIZED_KEYS_FILE:-/run/secrets/authorized_keys}
workspace=${WORKSPACE_DIR:-/workspace}

case "$enable_ssh:$enable_mlflow" in
  0:0|0:1|1:0|1:1) ;;
  *) echo "ENABLE_SSH and ENABLE_MLFLOW must be 0 or 1" >&2; exit 2 ;;
esac
if [[ "$enable_ssh" == 1 && ! -s "$keys_file" ]]; then
  echo "SSH requires a nonempty read-only public authorized_keys file at $keys_file" >&2
  exit 2
fi
if [[ "${1:-}" == --check ]]; then
  echo "Configuration OK: SSH=$enable_ssh MLflow=$enable_mlflow; Jupyter authentication stays enabled"
  exit 0
elif [[ $# -gt 0 ]]; then
  echo "Usage: start-gpu-services [--check]" >&2
  exit 2
fi

children=()
stop_children() {
  trap - TERM INT EXIT
  if [[ ${#children[@]} -gt 0 ]]; then
    kill -TERM "${children[@]}" 2>/dev/null || true
    wait "${children[@]}" 2>/dev/null || true
  fi
}
trap stop_children TERM INT EXIT

if [[ "$enable_ssh" == 1 ]]; then
  # Unique host identity per container; never generate a client/user private key.
  mkdir -p /run/sshd
  ssh-keygen -A
  /usr/sbin/sshd -t -o "AuthorizedKeysFile=$keys_file"
  /usr/sbin/sshd -D -e -o "AuthorizedKeysFile=$keys_file" &
  children+=("$!")
fi

if [[ "$enable_mlflow" == 1 ]]; then
  runuser -u developer -- mkdir -p "$workspace/mlflow/artifacts"
  # MLflow has no authentication here: bind ONLY the container's loopback interface.
  runuser -u developer -- mlflow server --host 127.0.0.1 --port 6006 \
    --backend-store-uri "sqlite:///$workspace/mlflow/mlflow.db" \
    --default-artifact-root "file://$workspace/mlflow/artifacts" &
  children+=("$!")
fi

# Jupyter generates its own token; do not disable auth or print tokens in our wrapper.
runuser -u developer -- jupyter lab \
  --ServerApp.ip=0.0.0.0 --ServerApp.port=8888 \
  --ServerApp.open_browser=False --ServerApp.root_dir="$workspace" &
children+=("$!")
set +e
wait -n "${children[@]}"
status=$?
set -e
exit "$status"
