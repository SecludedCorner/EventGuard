"""Read bounded, explicitly allowed manifests. Never run a tool or dependency."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import itertools
from pathlib import Path
import re
import stat
import tomllib

KNOWN_NAMES = frozenset({"Cargo.lock", "Cargo.toml", "rust-toolchain.toml", "pyproject.toml", "uv.lock"})
DEFAULT_MAX_AGE_SECONDS = 86400  # Existing static-inventory freshness policy.
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+~:!-]{0,159}$")
_BLOCKED_PARTS = frozenset({".git", ".codex", ".ssh", ".aws", ".azure", ".gnupg", "node_modules", "target", ".venv"})
_PRIVATE_NAMES = frozenset({"auth.json", "credentials.json", "secrets.json", "token.json", "tokens.json", "config.json", "settings.json", "package-lock.json"})
_FACTS = {"features", "feature_state", "optional", "tls_backend", "root_source", "deployed", "running", "module_present", "module_builtin", "module_loaded", "service_enabled", "reachable", "backport", "backport_evidence", "distribution", "distribution_version", "architecture", "host_kernel", "container", "source_url", "observed_at", "max_age_seconds", "embedded_components"}


def _now(value=None):
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bounded_int(config, key, default, upper):
    value = config.get(key, default)
    return value if type(value) is int and 1 <= value <= upper else default


def _ref(path):
    return hashlib.sha256(str(path.absolute()).encode("utf-8")).hexdigest()[:24]


def _no_links(path):
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("link_refused")
        if item.name.lower() in _BLOCKED_PARTS:
            raise ValueError("private_or_build_path_refused")


def _read(path, limit):
    _no_links(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("not_regular_file")
    if before.st_size > limit:
        raise ValueError("file_size_limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        current = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError("file_changed_during_read")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("file_size_limit")
        _no_links(path)
        after = os.fstat(descriptor)
        if current.st_size != after.st_size or current.st_mtime_ns != after.st_mtime_ns:
            raise ValueError("file_changed_during_read")
        return data
    finally:
        os.close(descriptor)


def _fact_values(values):
    if not isinstance(values, dict):
        return {}
    output = {}
    for key, value in values.items():
        if key not in _FACTS:
            continue
        if key == "features" and isinstance(value, dict):
            output[key] = {k: v for k, v in list(value.items())[:128] if isinstance(k, str) and _NAME.fullmatch(k) and type(v) is bool}
        elif key == "embedded_components" and isinstance(value, list):
            output[key] = [v for v in value[:128] if isinstance(v, str) and _NAME.fullmatch(v)]
        elif key == "backport_evidence" and isinstance(value, dict):
            safe = {k: v for k, v in value.items() if k in {"advisory_id", "package_version", "vendor_url", "status"} and isinstance(v, str) and len(v) <= 512 and not any(ord(c) < 32 or ord(c) == 127 for c in v)}
            output[key] = safe
        elif type(value) is bool or value is None or type(value) is int and 0 <= value <= 2**31:
            output[key] = value
        elif isinstance(value, str) and len(value) <= 512 and not any(ord(c) < 32 or ord(c) == 127 for c in value):
            output[key] = value
    return output


def collect_inventory(config: dict, now: str | None = None) -> dict:
    """Collect only inventory.paths. Directory entries contain known manifest names only."""
    settings = config.get("inventory", config)
    if not isinstance(settings, dict):
        settings = {}
    timestamp = _now(now)
    assets, coverage = [], []
    max_age = settings.get("max_age_seconds", DEFAULT_MAX_AGE_SECONDS)
    if type(max_age) is not int or not 1 <= max_age <= 30 * 86400:
        return {"collected_at": timestamp, "max_age_seconds": None, "assets": [],
                "coverage": [{"status": "error", "reason_codes": ["invalid_inventory_max_age"]}], "status": "unknown"}
    synthetic_data=[False]
    maximum = _bounded_int(settings, "max_files", 128, 1024)
    max_assets = _bounded_int(settings, "max_assets", 2048, 10000)
    file_limit = _bounded_int(settings, "max_file_bytes", 2 * 1024 * 1024, 8 * 1024 * 1024)
    depth_limit = _bounded_int(settings, "max_depth", 2, 8)
    paths = settings.get("paths", [])
    if not isinstance(paths, list) or len(paths) > 128:
        return {"collected_at": timestamp, "max_age_seconds": max_age, "assets": [], "coverage": [{"status": "error", "reason_codes": ["invalid_inventory_paths"]}], "status": "unknown"}

    def add(ecosystem, component, version, path, kind, facts=None, requirement=None):
        if not isinstance(component, str) or not _NAME.fullmatch(component):
            raise ValueError("invalid_component_name")
        if version is not None and (not isinstance(version, str) or not _VERSION.fullmatch(version)):
            raise ValueError("invalid_component_version")
        if len(assets) >= max_assets:
            raise ValueError("asset_count_limit")
        clean = {"feature_state": "unknown", "tls_backend": "unknown", "root_source": "unknown", "deployed": "unknown", "running": "unknown"}
        clean.update(_fact_values(facts))
        origin = {"kind": kind, "file_ref": _ref(path), "filename": path.name, "user_asserted": kind == "user_asserted"}
        identity = json.dumps([ecosystem, component, version, origin["file_ref"], clean], sort_keys=True).encode("utf-8")
        asset = {"asset_id": hashlib.sha256(identity).hexdigest()[:32], "ecosystem": ecosystem, "component": component, "version": version, "origin": origin, "facts": clean,
                 "observed_at": clean.get("observed_at") if kind == "user_asserted" else timestamp}
        if isinstance(requirement, str) and len(requirement) <= 256 and not any(ord(c) < 32 for c in requirement):
            asset["declared_requirement"] = requirement
        assets.append(asset)

    def parse(path, kind, data):
        if kind == "facts":
            decoded = json.loads(data)
            if isinstance(decoded,dict) and decoded.get("synthetic") is True:
                synthetic_data[0]=True
            rows = decoded.get("assets") if isinstance(decoded, dict) else None
            if not isinstance(rows, list) or len(rows) > max_assets:
                raise ValueError("invalid_facts_schema")
            for row in rows:
                if not isinstance(row, dict) or row.get("ecosystem") not in {"rust", "cargo", "python", "linux", "debian", "rpm", "tool", "system"}:
                    raise ValueError("invalid_facts_asset")
                add(row["ecosystem"], row.get("component"), row.get("version"), path, "user_asserted", row.get("facts"))
            return
        decoded = tomllib.loads(data.decode("utf-8-sig"))
        if path.name in {"Cargo.lock", "uv.lock"}:
            rows = decoded.get("package", [])
            if not isinstance(rows, list):
                raise ValueError("invalid_lock_schema")
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("invalid_lock_schema")
                add("rust" if path.name == "Cargo.lock" else "python", row.get("name"), row.get("version"), path, "lockfile")
        elif path.name == "Cargo.toml":
            package = decoded.get("package", {})
            if isinstance(package, dict) and isinstance(package.get("name"), str):
                add("rust", package["name"], package.get("version") if isinstance(package.get("version"), str) else None, path, "manifest")
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                entries = decoded.get(section, {})
                if not isinstance(entries, dict):
                    raise ValueError("invalid_manifest_dependencies")
                for name, dependency in entries.items():
                    info = dependency if isinstance(dependency, dict) else {"version": dependency}
                    add("rust", info.get("package", name), None, path, "manifest_requirement", {"optional": info.get("optional", False), "feature_state": "declared_only", "features": {v: True for v in info.get("features", []) if isinstance(v, str)}}, info.get("version"))
        elif path.name == "rust-toolchain.toml":
            channel = decoded.get("toolchain", {}).get("channel")
            add("tool", "rust-toolchain", channel if isinstance(channel, str) and _VERSION.fullmatch(channel) else None, path, "toolchain_declaration")
        elif path.name == "pyproject.toml":
            project = decoded.get("project", {})
            if isinstance(project, dict) and isinstance(project.get("name"), str):
                add("python", project["name"], project.get("version") if isinstance(project.get("version"), str) else None, path, "manifest")
            # requires-python and dependency constraints are not installed versions.
            tool = decoded.get("tool", {})
            if isinstance(tool, dict) and "uv" in tool:
                add("tool", "uv", None, path, "tool_configuration", {"embedded_components": []})

    pending = []
    directories_seen = 0
    for entry in paths:
        kind = "manifest"
        if isinstance(entry, dict):
            raw, kind = entry.get("path"), entry.get("kind", "manifest")
        else:
            raw = entry
        if not isinstance(raw, str) or not raw or kind not in {"manifest", "facts"}:
            coverage.append({"status": "error", "reason_codes": ["invalid_inventory_path"]})
            continue
        path = Path(raw).absolute()
        try:
            if path.name.lower() in _PRIVATE_NAMES or path.name.startswith("."):
                raise ValueError("private_file_refused")
            _no_links(path)
            if path.is_dir():
                if kind == "facts":
                    raise ValueError("facts_requires_explicit_file")
                stack = [(path, 0)]
                while stack:
                    folder, depth = stack.pop()
                    directories_seen += 1
                    if directories_seen > maximum:
                        raise ValueError("directory_count_limit")
                    _no_links(folder)
                    children = list(itertools.islice(folder.iterdir(), maximum + 1))
                    if len(children) > maximum:
                        raise ValueError("directory_entry_limit")
                    for child in sorted(children, key=lambda p: p.name):
                        if child.name in KNOWN_NAMES and child.is_file():
                            pending.append((child, kind))
                        elif depth < depth_limit and child.name.lower() not in _BLOCKED_PARTS and child.is_dir():
                            _no_links(child)
                            stack.append((child, depth + 1))
                        if len(pending) > maximum or len(stack) > maximum:
                            raise ValueError("file_count_limit")
            else:
                if kind != "facts" and path.name not in KNOWN_NAMES:
                    raise ValueError("file_type_not_allowed")
                if kind == "facts" and path.suffix.lower() != ".json":
                    raise ValueError("facts_requires_json")
                pending.append((path, kind))
        except (OSError, ValueError) as error:
            coverage.append({"file_ref": _ref(path), "status": "denied" if isinstance(error, PermissionError) else "error", "reason_codes": [str(error) if isinstance(error, ValueError) else "path_unavailable"], "error_type": type(error).__name__})
    seen = set()
    for path, kind in pending[:maximum]:
        key = str(path).casefold() if os.name == "nt" else str(path)
        if key in seen:
            continue
        seen.add(key)
        start = len(assets)
        try:
            data = _read(path, file_limit)
            parse(path, kind, data)
            coverage.append({"file_ref": _ref(path), "status": "success", "reason_codes": [], "asset_count": len(assets) - start, "content_hash": hashlib.sha256(data).hexdigest()})
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            del assets[start:]
            code = str(error) if type(error) is ValueError else "parse_failed" if not isinstance(error, OSError) else "read_failed"
            coverage.append({"file_ref": _ref(path), "status": "denied" if isinstance(error, PermissionError) else "error", "reason_codes": [code], "error_type": type(error).__name__})
    if len(pending) > maximum:
        coverage.append({"status": "error", "reason_codes": ["file_count_limit"]})
    failures = any(row["status"] != "success" for row in coverage)
    return {"collected_at": timestamp, "max_age_seconds": max_age, "assets": assets, "coverage": coverage,"synthetic":synthetic_data[0], "status": "partial" if failures and assets else "unknown" if failures or not coverage else "success"}
