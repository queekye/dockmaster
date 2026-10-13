"""Narrow, explicit container-cache cleanup; no host or shell deletion."""

from pathlib import PurePosixPath
from typing import Iterable, List

DEFAULT_CLEANUP_PATHS = ["/tmp/dockmaster", "/var/cache/dockmaster"]
ALLOWED_CACHE_ROOTS = ("/tmp", "/var/cache", "/root/.cache")


def validate_cleanup_path(path: str) -> str:
    """Require one exact descendant of an allowed cache root."""
    if not isinstance(path, str) or not path or any(c in path for c in "\x00\n\r*?[]"):
        raise ValueError("Cleanup requires exact absolute paths, without glob/control characters")
    parsed = PurePosixPath(path)
    if not parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError("Cleanup path must be absolute and cannot traverse parents")
    normalized = str(parsed)
    if not any(normalized.startswith(root + "/") for root in ALLOWED_CACHE_ROOTS):
        raise ValueError("Cleanup is restricted to descendants of /tmp, /var/cache or /root/.cache")
    return normalized


def cleanup_container_paths(container, paths: Iterable[str]) -> List[str]:
    """Validate every path first; refuse resolved symlinks escaping cache roots.

    The container needs readlink with -f and rm with -- (for example GNU coreutils).
    The admin must control cache-directory contents during cleanup; this is not a
    defense against concurrent hostile symlink replacement inside the container.
    """
    normalized_paths = [validate_cleanup_path(path) for path in paths]
    removed = []
    for path in normalized_paths:
        resolved = container.exec_run(["readlink", "-f", "--", path])
        if resolved.exit_code != 0 or not resolved.output.strip():
            raise RuntimeError("Cannot resolve cleanup path; no removal issued for " + path)
        resolved_path = resolved.output.decode("utf-8").strip()
        validate_cleanup_path(resolved_path)
        result = container.exec_run(["rm", "-rf", "--", resolved_path])
        if result.exit_code != 0:
            raise RuntimeError("Container cleanup failed for " + path)
        removed.append(resolved_path)
    return removed
