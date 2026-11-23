"""Core application runtime for 0rb1t."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .config import (
    config_dir,
    get_path,
    global_config_path,
    load_config,
    parse_value,
    project_config_path,
    reset_global_config,
    save_global_config,
    set_path,
)
from .context import clear_context, load_context, remove_context, set_context
from .engines.base import EngineRequest, EngineResponse
from .engines.registry import available_engines, build_engine
from .errors import CommandError, ConfigError, EngineError
from .integrations.discord_rpc import DiscordConfig, DiscordRPC, build_activity
from .plugins.loader import PluginContext, PluginManager


@dataclass
class CommandResult:
    ok: bool = True
    message: str = ""
    clear: bool = False
    exit: bool = False
    new_session: bool = False
    session_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class App:
    def __init__(self, cwd: str | Path | None = None) -> None:
        self.cwd = Path(cwd or Path.cwd()).resolve()
        self.config = load_config(self.cwd)
        self.plugins = PluginManager()
        self.engine = self._build_engine()
        self.discord = DiscordRPC()
        self.discord_last_status: dict[str, Any] = {
            "enabled": False,
            "client_id_configured": False,
            "client_detected": False,
            "connected": False,
            "last_update_ok": None,
            "last_error": "",
            "last_socket": "",
        }
        self._builtin_commands()
        self._load_plugins()

    def _build_engine(self):
        return build_engine(self.config)

    def reload(self) -> None:
        self.config = load_config(self.cwd)
        self.engine = self._build_engine()

    def _builtin_commands(self) -> None:
        pm = self.plugins
        pm.register_command("help", self.cmd_help, help="Show commands")
        pm.register_command("exit", self.cmd_exit, help="Exit 0rb1t", aliases=["quit", "q"])
        pm.register_command("clear", self.cmd_clear, help="Clear screen")
        pm.register_command("new", self.cmd_new, help="Start a fresh session")
        pm.register_command("session", self.cmd_session, help="Show current session id")
        pm.register_command("theme", self.cmd_theme, help="List/switch UI themes")
        pm.register_command("name", self.cmd_name, help="Get/set assistant display name")
        pm.register_command("config", self.cmd_config, help="Get/set/reset config")
        pm.register_command("profile", self.cmd_profile, help="List or switch profiles")
        pm.register_command("engine", self.cmd_engine, help="Show/switch engine and capabilities")
        pm.register_command("plugins", self.cmd_plugins, help="List loaded plugins")
        pm.register_command("context", self.cmd_context, help="Manage project/global context")
        pm.register_command("discord", self.cmd_discord, help="Discord Rich Presence status/controls")
        pm.register_command("about", self.cmd_about, help="Show environment information")
        pm.register_command("model", self.cmd_model, help="Show active/configured model")
        pm.register_command("version", self.cmd_version, help="Show version")

    def _load_plugins(self) -> None:
        pcfg = self.config.get("plugins", {})
        if not pcfg.get("enabled", True):
            return
        paths = []
        # default user plugin dir
        paths.append(config_dir() / "plugins")
        # project plugin dir
        paths.append(self.cwd / ".0rb1t" / "plugins")
        # configured extra paths
        for p in pcfg.get("paths", []) or []:
            try:
                pp = Path(str(p)).expanduser()
                if not pp.is_absolute():
                    pp = (self.cwd / pp).resolve()
                paths.append(pp)
            except Exception:
                continue
        ctx = PluginContext(app_version=__version__, config=self.config, data_dir=config_dir(), cwd=self.cwd)
        self.plugins.load_from_paths(paths, ctx)
        self.plugins.emit("plugins.loaded", {"count": len(self.plugins.loaded), "errors": list(self.plugins.errors)})

    # --- Discord ---
    def discord_config(self) -> DiscordConfig:
        d = self.config.get("integrations", {}).get("discord", {})
        if not isinstance(d, dict):
            d = {}
        return DiscordConfig(
            enabled=bool(d.get("enabled", False)),
            client_id=str(d.get("client_id", "") or ""),
            large_image=str(d.get("large_image", "orb1t") or "orb1t"),
            large_text=str(d.get("large_text", "0rb1t") or "0rb1t"),
        )

    def update_discord_presence(self) -> dict[str, Any]:
        cfg = self.discord_config()
        status = {
            "enabled": cfg.enabled,
            "client_id_configured": bool(cfg.client_id),
            "client_detected": bool(self.discord.discover_socket()),
            "connected": self.discord.connected,
            "last_update_ok": self.discord.last_update_ok,
            "last_error": self.discord.last_error,
            "last_socket": self.discord.last_socket,
        }
        if not cfg.enabled:
            status["last_error"] = "disabled"
            self.discord_last_status = status
            return status
        if not cfg.client_id:
            status["last_error"] = "missing client_id (set integrations.discord.client_id)"
            self.discord_last_status = status
            return status
        try:
            ok_conn = self.discord.connect(cfg.client_id)
            status["connected"] = ok_conn
            status["last_socket"] = self.discord.last_socket
            status["client_detected"] = bool(self.discord.discover_socket()) or ok_conn
            if not ok_conn:
                status["last_update_ok"] = False
                status["last_error"] = self.discord.last_error or "could not connect to Discord IPC"
                self.discord_last_status = status
                return status
            ai_name = str(self.config.get("ui", {}).get("name", "0rb1t"))
            ok = self.discord.send_activity(build_activity(ai_name, cfg))
            status["connected"] = self.discord.connected
            status["last_update_ok"] = ok
            status["last_error"] = self.discord.last_error
            status["last_socket"] = self.discord.last_socket
        except Exception as e:
            status["last_update_ok"] = False
            status["last_error"] = str(e)
            try:
                self.discord.close()
            except Exception:
                pass
        self.discord_last_status = status
        return status

    def shutdown_integrations(self) -> None:
        try:
            self.discord.clear()
        except Exception:
            try:
                self.discord.close()
            except Exception:
                pass

    # --- command handlers ---
    def cmd_help(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        lines = ["Commands"]
        for name in sorted(self.plugins.commands):
            spec = self.plugins.commands[name]
            alias = f" ({', '.join(spec.aliases)})" if spec.aliases else ""
            src = f" [{spec.source}]" if spec.source != "builtin" else ""
            lines.append(f"  /{name:<10} {spec.help}{alias}{src}".rstrip())
        lines.append("")
        lines.append("Tips: /engine list, /engine use <name>, /config get ui.theme, /config set ui.theme cyan")
        return CommandResult(message="\n".join(lines))

    def cmd_exit(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        return CommandResult(exit=True, message="disconnecting.")

    def cmd_clear(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        return CommandResult(clear=True)

    def cmd_new(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        return CommandResult(new_session=True, message="new session started.")

    def cmd_session(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args
        sid = ctx.get("session_id")
        return CommandResult(message=sid or "no active session yet")

    def cmd_theme(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        from . import ui

        if not args:
            cur = self.config.get("ui", {}).get("theme", "purple")
            lines = ["Themes"]
            for n in ui.theme_names():
                lines.append(f"  {'*' if n == cur else ' '} {n}")
            lines.append("Use /theme <name>")
            return CommandResult(message="\n".join(lines))
        name = args[0].lower()
        if not ui.set_theme(name):
            return CommandResult(ok=False, message=f"unknown theme '{name}'. Try /theme")
        self.config = set_path(self.config, "ui.theme", ui.THEME_NAME)
        save_global_config(self.config)
        return CommandResult(message=f"theme set to {ui.THEME_NAME}", clear=True)

    def cmd_name(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        from . import ui

        if not args:
            return CommandResult(message=f"current name: {ui.APP_NAME}\nUse /name <name>")
        name = " ".join(args).strip()[:32]
        ui.set_name(name)
        self.config = set_path(self.config, "ui.name", ui.APP_NAME)
        save_global_config(self.config)
        self.update_discord_presence()
        return CommandResult(message=f"name set to {ui.APP_NAME}")

    def cmd_config(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = ctx
        if not args:
            return CommandResult(message=self._config_summary())
        sub = args[0].lower()
        if sub == "reset":
            self.config = reset_global_config()
            self.reload()
            self.update_discord_presence()
            return CommandResult(message="config reset to defaults", clear=True)
        if sub == "path":
            return CommandResult(message=f"global: {global_config_path()}\nproject: {project_config_path(self.cwd)}")
        if sub == "get" and len(args) >= 2:
            key = args[1]
            val = get_path(self.config, key)
            return CommandResult(message=f"{key} = {val!r}")
        if sub == "set" and len(args) >= 3:
            key = args[1]
            raw = " ".join(args[2:])
            val = parse_value(raw)
            self.config = set_path(self.config, key, val)
            # validate by reloading through save
            try:
                save_global_config(self.config)
                self.reload()
            except ConfigError as e:
                return CommandResult(ok=False, message=str(e))
            if key.startswith("ui.name") or key.startswith("integrations.discord"):
                self.update_discord_presence()
            return CommandResult(message=f"set {key}", clear=key.startswith("ui."))
        return CommandResult(ok=False, message="usage: /config [path|get <key>|set <key> <value>|reset]")

    def cmd_profile(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = ctx
        profiles = self.config.get("profiles", {}).get("items", {})
        active = self.config.get("profiles", {}).get("active", "default")
        if not args or args[0].lower() == "list":
            lines = ["Profiles"]
            for name in sorted(profiles):
                lines.append(f"  {'*' if name == active else ' '} {name}")
            lines.append("Use /profile use <name> or /profile add <name>")
            return CommandResult(message="\n".join(lines))
        sub = args[0].lower()
        if sub == "use" and len(args) >= 2:
            name = args[1]
            if name not in profiles:
                return CommandResult(ok=False, message=f"unknown profile '{name}'")
            self.config = set_path(self.config, "profiles.active", name)
            save_global_config(self.config)
            self.reload()
            return CommandResult(message=f"active profile: {name}", clear=True)
        if sub == "add" and len(args) >= 2:
            name = args[1]
            if name in profiles:
                return CommandResult(ok=False, message=f"profile '{name}' already exists")
            profiles[name] = {"name": name, "engine": {}, "persona_prompt": None}
            self.config = set_path(self.config, "profiles.items", profiles)
            save_global_config(self.config)
            return CommandResult(message=f"profile added: {name}")
        return CommandResult(ok=False, message="usage: /profile [list|use <name>|add <name>]")

    def cmd_engine(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = ctx
        if args and args[0].lower() in {"use", "switch"}:
            if len(args) < 2:
                return CommandResult(ok=False, message="usage: /engine use <name>")
            name = args[1].lower().strip()
            if name not in available_engines():
                return CommandResult(ok=False, message=f"unknown engine '{name}'. Available: {', '.join(available_engines())}")
            self.config = set_path(self.config, "engine.name", name)
            try:
                save_global_config(self.config)
                old = self.engine
                self.reload()
                try:
                    old.shutdown()
                except Exception:
                    pass
            except Exception as e:
                return CommandResult(ok=False, message=f"failed to switch engine: {e}")
            return CommandResult(message=f"active engine: {name}", clear=True)

        if args and args[0].lower() in {"list", "adapters"}:
            return CommandResult(message="Engines\n  " + "\n  ".join(available_engines()))

        info = self.engine.info() if hasattr(self.engine, "info") else {"name": getattr(self.engine, "name", "unknown")}
        caps = info.get("capabilities", {}) if isinstance(info, dict) else {}
        lines = [
            "Engine",
            f"  active: {info.get('name')}",
            f"  installed: {info.get('installed')}",
            f"  healthy: {info.get('healthy')}",
            f"  status: {info.get('status')}",
            f"  available_adapters: {', '.join(available_engines())}",
        ]
        for k in ("command", "auto", "model", "agent", "path"):
            if k in info and info.get(k) is not None:
                lines.append(f"  {k}: {info.get(k)}")
        if isinstance(caps, dict) and caps:
            lines.append("  capabilities:")
            for cap, supported in caps.items():
                mark = "yes" if supported else "no"
                lines.append(f"    - {cap}: {mark}")
        lines.append("  commands: /engine list | /engine use <name>")
        return CommandResult(message="\n".join(lines))

    def cmd_plugins(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        lines = ["Plugins", f"  enabled: {self.config.get('plugins', {}).get('enabled', True)}"]
        if self.plugins.loaded:
            lines.append("  loaded:")
            for p in self.plugins.loaded:
                lines.append(f"    - {p}")
        else:
            lines.append("  loaded: none")
        if self.plugins.errors:
            lines.append("  errors:")
            for e in self.plugins.errors:
                lines.append(f"    - {e}")
        return CommandResult(message="\n".join(lines))

    def cmd_context(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = ctx
        if len(args) < 2:
            return CommandResult(ok=False, message="usage: /context <global|project> <list|set|get|remove|clear> ...")
        scope = args[0].lower()
        if scope not in {"global", "project"}:
            return CommandResult(ok=False, message="scope must be global or project")
        action = args[1].lower()
        if action == "list":
            data = load_context(scope, self.cwd).get("items", {})
            if not data:
                return CommandResult(message=f"{scope} context: empty")
            lines = [f"{scope} context"]
            for k, v in data.items():
                vv = str(v)
                if len(vv) > 80:
                    vv = vv[:77] + "..."
                lines.append(f"  {k}: {vv}")
            return CommandResult(message="\n".join(lines))
        if action == "set" and len(args) >= 4:
            key = args[2]
            value = " ".join(args[3:])
            set_context(scope, self.cwd, key, value)
            return CommandResult(message=f"{scope} context set: {key}")
        if action == "get" and len(args) >= 3:
            data = load_context(scope, self.cwd).get("items", {})
            key = args[2]
            if key not in data:
                return CommandResult(ok=False, message=f"missing key: {key}")
            return CommandResult(message=f"{key} = {data[key]!r}")
        if action == "remove" and len(args) >= 3:
            ok = remove_context(scope, self.cwd, args[2])
            return CommandResult(ok=ok, message=("removed" if ok else "missing key"))
        if action == "clear":
            clear_context(scope, self.cwd)
            return CommandResult(message=f"{scope} context cleared")
        return CommandResult(ok=False, message="usage: /context <global|project> <list|set|get|remove|clear> ...")

    def cmd_discord(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = ctx
        sub = args[0].lower() if args else "status"
        cfg = self.discord_config()
        if sub in {"status", ""}:
            st = self.discord_last_status.copy()
            st["enabled"] = cfg.enabled
            st["client_id_configured"] = bool(cfg.client_id)
            st["client_detected"] = bool(self.discord.discover_socket()) or bool(st.get("client_detected"))
            st["connected"] = self.discord.connected
            st["last_socket"] = self.discord.last_socket or st.get("last_socket", "")
            st["last_error"] = self.discord.last_error or st.get("last_error", "")
            st["last_update_ok"] = self.discord.last_update_ok if self.discord.last_update_ok is not None else st.get("last_update_ok")
            lines = ["Discord Rich Presence"]
            lines.append(f"  enabled: {st['enabled']}")
            lines.append(f"  client_id: {'configured' if st['client_id_configured'] else 'missing'}")
            lines.append(f"  client_detected: {st['client_detected']}")
            lines.append(f"  ipc_connected: {st['connected']}")
            lines.append(f"  last_update_ok: {st['last_update_ok']}")
            if st.get("last_socket"):
                lines.append(f"  socket: {st['last_socket']}")
            if st.get("last_error"):
                lines.append(f"  last_error: {st['last_error']}")
            lines.append("")
            activity = build_activity(str(self.config.get("ui", {}).get("name", "0rb1t")), cfg)
            lines.append(f"  details: {activity['details']} (rotates every minute)")
            lines.append(f"  state: {activity['state']}")
            lines.append("  button: GitHub -> https://github.com/y0x1a/0rb1t")
            if not cfg.enabled:
                lines.append("")
                lines.append("  To enable: /config set integrations.discord.enabled true")
            if not cfg.client_id:
                lines.append("  To configure: set integrations.discord.client_id to your Discord Application ID")
                lines.append("  Optional: integrations.discord.large_image (Discord asset key)")
            return CommandResult(message="\n".join(lines))
        if sub == "reconnect":
            st = self.update_discord_presence()
            return CommandResult(ok=bool(st.get("last_update_ok") or st.get("connected") or st.get("enabled") is False), message="Discord reconnect attempted. Use /discord status for details.")
        if sub in {"enable", "on"}:
            self.config = set_path(self.config, "integrations.discord.enabled", True)
            save_global_config(self.config); self.reload(); self.update_discord_presence()
            return CommandResult(message="Discord Rich Presence enabled (if client_id is configured).")
        if sub in {"disable", "off"}:
            self.config = set_path(self.config, "integrations.discord.enabled", False)
            save_global_config(self.config); self.reload(); self.shutdown_integrations()
            return CommandResult(message="Discord Rich Presence disabled.")
        return CommandResult(ok=False, message="usage: /discord [status|reconnect|enable|disable]")

    def cmd_about(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        ui = self.config.get("ui", {})
        eng = self.config.get("engine", {})
        info = self.engine.info() if hasattr(self.engine, "info") else {}
        model = eng.get("model") or "(engine default)"
        lines = [
            "About 0rb1t",
            f"  version: {__version__}",
            f"  assistant: {ui.get('name','0rb1t')}",
            f"  active engine: {eng.get('name','unknown')}",
            f"  engine status: {info.get('status','unknown')}",
            f"  model: {model}",
            f"  cwd: {self.cwd}",
            f"  global config: {global_config_path()}",
        ]
        return CommandResult(message="\n".join(lines))

    def cmd_model(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        eng = self.config.get("engine", {})
        model = eng.get("model")
        name = eng.get("name", "unknown")
        lines = ["Model"]
        lines.append(f"  active engine: {name}")
        lines.append(f"  configured model: {model or '(engine default)'}")
        # Capability-aware discovery
        if hasattr(self.engine, "supports") and self.engine.supports("models"):
            try:
                models = self.engine.list_models()  # type: ignore[attr-defined]
                if models:
                    lines.append("  available models:")
                    for m in models[:20]:
                        lines.append(f"    - {m}")
                else:
                    lines.append("  available models: none reported")
            except Exception as e:
                lines.append(f"  available models: unavailable ({e})")
        else:
            lines.append("  available models: not exposed by active engine adapter")
            lines.append("  tip: set with /config set engine.model \"provider/model\"")
        return CommandResult(message="\n".join(lines))

    def cmd_version(self, args: list[str], ctx: dict[str, Any]) -> CommandResult:
        _ = args, ctx
        return CommandResult(message=f"0rb1t v{__version__}")

    def _config_summary(self) -> str:
        c = self.config
        ui = c.get("ui", {})
        eng = c.get("engine", {})
        prof = c.get("profiles", {})
        discord = c.get("integrations", {}).get("discord", {})
        return "\n".join([
            "Config",
            f"  ui.theme: {ui.get('theme')}",
            f"  ui.name: {ui.get('name')}",
            f"  ui.alt_screen: {ui.get('alt_screen')}",
            f"  engine.name: {eng.get('name')}",
            f"  engine.command: {eng.get('command')}",
            f"  engine.auto: {eng.get('auto')}",
            f"  profiles.active: {prof.get('active')}",
            f"  integrations.discord.enabled: {discord.get('enabled')}",
            f"  integrations.discord.client_id: {'(set)' if discord.get('client_id') else '(not set)'}",
            f"  global: {global_config_path()}",
            f"  project: {project_config_path(self.cwd)}",
        ])

    # --- dispatch ---
    def dispatch_command(self, text: str, *, session_id: str | None = None) -> CommandResult:
        raw = text.strip()
        if not raw.startswith("/"):
            raise CommandError("not a command")
        parts = raw[1:].split()
        if not parts:
            return CommandResult(ok=False, message="empty command")
        name = parts[0].lower()
        args = parts[1:]
        spec = self.plugins.resolve_command(name)
        if not spec:
            return CommandResult(ok=False, message=f"unknown command: /{name}. Try /help")
        ctx = {"session_id": session_id, "cwd": str(self.cwd), "config": self.config}
        self.plugins.emit("command.before", {"name": spec.name, "args": args})
        try:
            res = spec.handler(args, ctx)
            if not isinstance(res, CommandResult):
                res = CommandResult(message=str(res))
        except SystemExit:
            raise
        except Exception as e:
            return CommandResult(ok=False, message=f"command error: {e}")
        self.plugins.emit("command.after", {"name": spec.name, "args": args, "ok": res.ok})
        return res

    def build_system_prompt(self) -> str:
        name = str(self.config.get("ui", {}).get("name", "0rb1t"))
        persona = str(self.config.get("persona", {}).get("prompt", ""))
        active = self.config.get("profiles", {}).get("active", "default")
        prof = self.config.get("profiles", {}).get("items", {}).get(active, {})
        prof_prompt = prof.get("persona_prompt")
        base = prof_prompt if isinstance(prof_prompt, str) and prof_prompt.strip() else persona
        try:
            return base.format(name=name)
        except Exception:
            return base.replace("{name}", name)

    def send(self, message: str, *, session_id: str | None = None) -> EngineResponse:
        self.plugins.emit("message.before", {"message": message, "session_id": session_id})
        eng_cfg = self.config.get("engine", {})
        req = EngineRequest(
            message=message,
            session_id=session_id,
            cwd=str(self.cwd),
            model=eng_cfg.get("model"),
            agent=eng_cfg.get("agent"),
            system_prompt=self.build_system_prompt(),
        )
        try:
            if hasattr(self.engine, "supports") and not self.engine.supports("send"):
                raise EngineError(
                    f"Active engine '{getattr(self.engine, 'name', 'unknown')}' does not support send",
                    code="unsupported_capability",
                    engine=getattr(self.engine, "name", None),
                    capability="send",
                )
            resp = self.engine.send(req)
        except EngineError:
            raise
        except Exception as e:
            raise EngineError(str(e), code="engine_runtime_error", engine=getattr(self.engine, "name", None)) from e
        self.plugins.emit("message.after", {"session_id": resp.session_id, "ok": not bool(resp.error)})
        return resp
