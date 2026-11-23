"""Plugin loading and API."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..errors import PluginError


@dataclass
class PluginContext:
    app_version: str
    config: dict[str, Any]
    data_dir: Path
    cwd: Path


class PluginAPI:
    """API exposed to plugins during registration."""

    def __init__(self, manager: "PluginManager", plugin_name: str) -> None:
        self._manager = manager
        self.plugin_name = plugin_name

    def register_command(self, name: str, handler: Callable[..., Any], *, help: str = "", aliases: list[str] | None = None) -> None:
        self._manager.register_command(name, handler, help=help, aliases=aliases or [], source=self.plugin_name)

    def register_hook(self, event: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._manager.register_hook(event, handler, source=self.plugin_name)

    def log(self, message: str) -> None:
        self._manager.logs.append(f"[{self.plugin_name}] {message}")


@dataclass
class CommandSpec:
    name: str
    handler: Callable[..., Any]
    help: str = ""
    aliases: list[str] = field(default_factory=list)
    source: str = "builtin"


class PluginManager:
    def __init__(self) -> None:
        self.commands: dict[str, CommandSpec] = {}
        self.aliases: dict[str, str] = {}
        self.hooks: dict[str, list[tuple[str, Callable[[dict[str, Any]], Any]]]] = {}
        self.loaded: list[str] = []
        self.errors: list[str] = []
        self.logs: list[str] = []

    def register_command(self, name: str, handler: Callable[..., Any], *, help: str = "", aliases: list[str] | None = None, source: str = "builtin") -> None:
        cmd = name.lower().lstrip("/")
        spec = CommandSpec(name=cmd, handler=handler, help=help, aliases=aliases or [], source=source)
        self.commands[cmd] = spec
        for a in spec.aliases:
            self.aliases[a.lower().lstrip("/")] = cmd

    def resolve_command(self, name: str) -> CommandSpec | None:
        key = name.lower().lstrip("/")
        key = self.aliases.get(key, key)
        return self.commands.get(key)

    def register_hook(self, event: str, handler: Callable[[dict[str, Any]], Any], *, source: str = "unknown") -> None:
        self.hooks.setdefault(event, []).append((source, handler))

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        data = dict(payload or {})
        results = []
        for source, handler in self.hooks.get(event, []):
            try:
                handler(data)
                results.append({"event": event, "source": source, "ok": True})
            except Exception as e:
                results.append({"event": event, "source": source, "ok": False, "error": str(e)})
        return results

    def load_from_paths(self, paths: list[Path], ctx: PluginContext) -> None:
        for path in paths:
            self.load_path(path, ctx)

    def load_path(self, path: Path, ctx: PluginContext) -> None:
        if not path.exists():
            return
        if path.is_dir():
            for p in sorted(path.glob("*.py")):
                if p.name.startswith("_"):
                    continue
                self.load_file(p, ctx)
            return
        if path.suffix == ".py":
            self.load_file(path, ctx)

    def load_file(self, file: Path, ctx: PluginContext) -> None:
        mod_name = f"orb1t_plugin_{file.stem}_{abs(hash(str(file))) & 0xFFFFFFFF:x}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, file)
            if spec is None or spec.loader is None:
                raise PluginError(f"cannot load spec for {file}")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            register = getattr(mod, "register", None)
            if not callable(register):
                raise PluginError(f"{file} has no callable register(api, ctx)")
            api = PluginAPI(self, plugin_name=file.stem)
            register(api, ctx)
            self.loaded.append(str(file))
        except Exception as e:
            self.errors.append(f"{file}: {e}")
