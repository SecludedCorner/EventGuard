"""Shared owned-data path checks; no optional protocol/backend imports."""
from pathlib import Path


class LocalWaitError(RuntimeError):
    """Compatibility error identity; only fixed reason codes are exposed."""


def _guard(path):
    path = Path(path)
    if ".." in path.parts:
        raise LocalWaitError("experiment_parent_path_rejected")
    path = path.absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise LocalWaitError("experiment_path_redirect_rejected")
    return path
