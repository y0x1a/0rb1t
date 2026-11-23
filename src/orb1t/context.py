"""Simple persistent context/memory storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import config_dir, ensure_dir


def global_context_path() -> Path:
    return config_dir() / "context.json"


def project_context_path(cwd: Path) -> Path:
    return cwd / ".0rb1t" / "context.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"items": {}}
    if not isinstance(data, dict):
        return {"items": {}}
    items = data.get("items")
    if not isinstance(items, dict):
        data["items"] = {}
    return data


def _save(path: Path, data: dict[str, Any]) -> None:
    ensure_dir(path)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_context(scope: str, cwd: Path) -> dict[str, Any]:
    path = global_context_path() if scope == "global" else project_context_path(cwd)
    return _load(path)


def set_context(scope: str, cwd: Path, key: str, value: str) -> None:
    path = global_context_path() if scope == "global" else project_context_path(cwd)
    data = _load(path)
    data.setdefault("items", {})[key] = value
    _save(path, data)


def remove_context(scope: str, cwd: Path, key: str) -> bool:
    path = global_context_path() if scope == "global" else project_context_path(cwd)
    data = _load(path)
    items = data.setdefault("items", {})
    if key in items:
        del items[key]
        _save(path, data)
        return True
    return False


def clear_context(scope: str, cwd: Path) -> None:
    path = global_context_path() if scope == "global" else project_context_path(cwd)
    _save(path, {"items": {}})
