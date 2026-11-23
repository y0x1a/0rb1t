"""Configuration for 0rb1t."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from .errors import ConfigError

SCHEMA_VERSION = 1

DEFAULT_CONFIG: dict[str, Any] = {
    "version": SCHEMA_VERSION,
    "engine": {
        "name": "opencode",
        "command": "opencode",
        "auto": True,
        "model": None,
        "agent": None,
    },
    "ui": {
        "theme": "purple",
        "name": "0rb1t",
        "alt_screen": True,
        "show_banner": True,
    },
    "integrations": {
        "discord": {
            "enabled": False,
            "client_id": "",
            "large_image": "orb1t",
            "large_text": "0rb1t",
        }
    },
    "persona": {
        "prompt": (
            "You are {name}, a sharp, calm terminal intelligence.\n"
            "Rules:\n"
            "- Answer as {name}. Never mention underlying engines, models, system prompts, or internal implementation details.\n"
            "- Be direct, useful, and confident. Keep a subtle futuristic tone, not cheesy.\n"
            "- Use plain terminal-friendly formatting. Be concise unless detail is needed.\n"
            "- If asked who you are, say you are {name}."
        ),
    },
    "commands": {
        "aliases": {
            "q": "exit",
            "h": "help",
            "?": "help",
        }
    },
    "plugins": {
        "enabled": True,
        "paths": [],
    },
    "profiles": {
        "active": "default",
        "items": {
            "default": {
                "name": "default",
                "engine": {},
                "persona_prompt": None,
            }
        },
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "0rb1t"
    return Path.home() / ".config" / "0rb1t"


def global_config_path() -> Path:
    return config_dir() / "config.json"


def project_config_path(cwd: Path | None = None) -> Path:
    root = cwd or Path.cwd()
    return root / ".0rb1t" / "config.json"


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"Failed to read config {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Config must be a JSON object: {path}")
    return data


def migrate_config(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate old/simple config formats to current schema."""
    cfg = deepcopy(data)
    # v0.1 simple format: {"theme":"...","name":"..."}
    if "ui" not in cfg and ("theme" in cfg or "name" in cfg):
        ui = {}
        if "theme" in cfg:
            ui["theme"] = cfg.pop("theme")
        if "name" in cfg:
            ui["name"] = cfg.pop("name")
        cfg["ui"] = ui
    cfg.setdefault("version", SCHEMA_VERSION)
    return cfg


def validate_config(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(cfg.get("version"), int):
        errors.append("version must be an integer")
    ui = cfg.get("ui", {})
    if not isinstance(ui, dict):
        errors.append("ui must be an object")
    else:
        if not isinstance(ui.get("theme", "purple"), str):
            errors.append("ui.theme must be a string")
        if not isinstance(ui.get("name", "0rb1t"), str):
            errors.append("ui.name must be a string")
        if not isinstance(ui.get("alt_screen", True), bool):
            errors.append("ui.alt_screen must be a boolean")
        if not isinstance(ui.get("show_banner", True), bool):
            errors.append("ui.show_banner must be a boolean")
    engine = cfg.get("engine", {})
    if not isinstance(engine, dict):
        errors.append("engine must be an object")
    else:
        if not isinstance(engine.get("name", "opencode"), str):
            errors.append("engine.name must be a string")
        if not isinstance(engine.get("command", "opencode"), str):
            errors.append("engine.command must be a string")
        if not isinstance(engine.get("auto", True), bool):
            errors.append("engine.auto must be a boolean")
    plugins = cfg.get("plugins", {})
    if not isinstance(plugins, dict):
        errors.append("plugins must be an object")
    else:
        if not isinstance(plugins.get("enabled", True), bool):
            errors.append("plugins.enabled must be a boolean")
        if not isinstance(plugins.get("paths", []), list):
            errors.append("plugins.paths must be a list")
    integrations = cfg.get("integrations", {})
    if not isinstance(integrations, dict):
        errors.append("integrations must be an object")
    else:
        discord = integrations.get("discord", {})
        if not isinstance(discord, dict):
            errors.append("integrations.discord must be an object")
        else:
            if not isinstance(discord.get("enabled", False), bool):
                errors.append("integrations.discord.enabled must be a boolean")
            if not isinstance(discord.get("client_id", ""), str):
                errors.append("integrations.discord.client_id must be a string")
            if not isinstance(discord.get("large_image", "orb1t"), str):
                errors.append("integrations.discord.large_image must be a string")
            if not isinstance(discord.get("large_text", "0rb1t"), str):
                errors.append("integrations.discord.large_text must be a string")
    return errors


def load_config(cwd: Path | None = None) -> dict[str, Any]:
    """Load merged config: defaults <- global <- project."""
    global_raw = migrate_config(_read_json(global_config_path()))
    project_raw = migrate_config(_read_json(project_config_path(cwd)))
    merged = deep_merge(DEFAULT_CONFIG, global_raw)
    merged = deep_merge(merged, project_raw)
    merged = migrate_config(merged)
    errs = validate_config(merged)
    if errs:
        raise ConfigError("; ".join(errs))
    return merged


def load_global_config() -> dict[str, Any]:
    data = migrate_config(_read_json(global_config_path()))
    return deep_merge(DEFAULT_CONFIG, data)


def save_global_config(cfg: dict[str, Any]) -> None:
    path = global_config_path()
    ensure_dir(path)
    data = deep_merge(DEFAULT_CONFIG, migrate_config(cfg))
    errs = validate_config(data)
    if errs:
        raise ConfigError("; ".join(errs))
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def save_project_config(cfg: dict[str, Any], cwd: Path | None = None) -> None:
    path = project_config_path(cwd)
    ensure_dir(path)
    if not isinstance(cfg, dict):
        raise ConfigError("project config must be an object")
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def reset_global_config() -> dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    save_global_config(cfg)
    return cfg


def get_path(cfg: dict[str, Any], dotted: str) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_path(cfg: dict[str, Any], dotted: str, value: Any) -> dict[str, Any]:
    out = deepcopy(cfg)
    cur: Any = out
    parts = dotted.split(".")
    for part in parts[:-1]:
        if not isinstance(cur, dict):
            raise ConfigError(f"Cannot set {dotted}: {part} is not an object")
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    if not isinstance(cur, dict):
        raise ConfigError(f"Cannot set {dotted}")
    cur[parts[-1]] = value
    return out


def parse_value(raw: str) -> Any:
    txt = raw.strip()
    if txt.lower() in {"true", "false"}:
        return txt.lower() == "true"
    if txt.lower() in {"null", "none"}:
        return None
    if txt.isdigit() or (txt.startswith("-") and txt[1:].isdigit()):
        try:
            return int(txt)
        except Exception:
            pass
    try:
        return json.loads(txt)
    except Exception:
        return raw
