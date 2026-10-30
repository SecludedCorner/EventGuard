"""Known Windows Codex runtime bundle: copy/hash only, never start a model."""
import hashlib
import shutil

from .acceptance_control import write_json
from .local_paths import _guard

REQUIRED = ('codex.exe', 'codex-code-mode-host.exe', 'codex-command-runner.exe',
            'codex-windows-sandbox-setup.exe')
MAX_BYTES = 1024 * 1024 * 1024


def file_hash(path):
    with _guard(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(executable):
    """Fail before model admission if a known companion is absent or invalid."""
    executable = _guard(executable)
    if executable.name != 'codex.exe':
        raise ValueError('codex_bundle_executable_required')
    if {item.name for item in executable.parent.iterdir()} - set(REQUIRED) - {'bundle.json', 'preflight'}:
        raise ValueError('codex_runtime_layout_unrecognized')
    files = {}
    for name in REQUIRED:
        path = _guard(executable.parent/name)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError('codex_runtime_bundle_incomplete')
        with path.open('rb') as stream:
            if stream.read(2) != b'MZ':
                raise ValueError('codex_runtime_executable_invalid')
        files[name] = dict(bytes=path.stat().st_size, sha256=file_hash(path))
    if sum(value['bytes'] for value in files.values()) > MAX_BYTES:
        raise ValueError('codex_runtime_bundle_capacity')
    return dict(kind='eventguard-windows-codex-bundle-v1', files=files)


def snapshot(executable, destination):
    """Copy the whole known flat version directory; leave partial failures intact."""
    executable, destination = _guard(executable), _guard(destination)
    original = inventory(executable)
    if {item.name for item in executable.parent.iterdir()} != set(REQUIRED):
        raise ValueError('codex_runtime_layout_unrecognized')
    destination.mkdir(parents=True, exist_ok=False)
    for name in REQUIRED:
        shutil.copyfile(_guard(executable.parent/name), _guard(destination/name))
    if inventory(destination/'codex.exe') != original or inventory(executable) != original:
        raise ValueError('codex_runtime_changed_during_snapshot')
    write_json(destination/'bundle.json', original)
    return original
