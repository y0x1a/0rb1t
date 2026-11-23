# 0rb1t Architecture

## Overview

0rb1t is a customizable terminal intelligence environment. It owns the user-facing experience, configuration, commands, plugins, and context. Execution backends are pluggable **engine adapters**.

OpenCode is the first supported adapter. Engine-specific logic stays in `engines/`; core runtime behavior should go through the adapter interface and registry.

## Modules

- `cli.py` - argparse entrypoint, one-shot mode, REPL/TUI event loop
- `terminal.py` - low-level terminal mode control (alt screen, raw mode, mouse, cleanup)
- `input_editor.py` - multiline input buffer and key/escape parser
- `tui.py` - viewport layout/rendering, scroll/follow behavior, fixed input dock
- `theme.py` - TUI color/theme helpers (dark purple identity)
- `app.py` - runtime orchestration, command dispatch, config/profile/plugin wiring, integration lifecycle
- `config.py` - defaults, migration, validation, merge/load/save, path helpers
- `context.py` - persistent global/project key-value context
- `errors.py` - base errors and normalized `EngineError`
- `engines/base.py` - engine capability contract and shared types
- `engines/opencode.py` - OpenCode adapter implementation
- `engines/registry.py` - adapter registry/factory (`build_engine`, `available_engines`, `register/unregister`)
- `plugins/loader.py` - plugin discovery, API, command/hook registration, isolation
- `integrations/discord_rpc.py` - optional Discord Rich Presence IPC client
- `ui.py` - legacy/static UI helpers (compat)
- `backend.py` - legacy compatibility wrapper over OpenCode adapter

## Engine capability system

Capabilities are explicit. Adapters declare support via `capabilities()`; core checks `supports()` / `require()` and never fakes unsupported behavior.

Current capability names:

- `health` - health/installation check
- `models` - model discovery
- `agents` - agent discovery
- `sessions.list` - list sessions
- `sessions.create` - create session
- `sessions.delete` - delete session
- `send` - send message and receive response
- `stream` - streaming responses
- `cancel` - cancel active request/session operation

Adapter contract (`EngineAdapter`): `capabilities()`, `supports()`, `health()`, `info()`, `send()`, and optional capability methods (`list_models`, `list_agents`, `list_sessions`, `create_session`, `delete_session`, `cancel`, `shutdown`).

Errors are normalized through `EngineError` (`message`, `code`, `engine`, `capability`, `detail`), with `UnsupportedCapabilityError` and `EngineUnavailableError` for common cases.

## Runtime flow

1. `cli.main` parses args and creates `App(cwd)`.
2. `App` loads merged config, builds the active engine via registry, registers builtins, loads plugins, and exposes integration lifecycle hooks.
3. One-shot mode calls `App.send` directly and prints plain output.
4. REPL/TUI mode initializes terminal modes, renders a scrollable transcript viewport with a fixed input dock, and processes key/mouse/resize events.
5. `/...` input dispatches commands via `PluginManager`; plain text is sent through `App.send` in a background worker while UI renders a thinking status.
6. Responses are appended to transcript state; session ID retained for continuity; Discord presence updates on start/name/config changes and clears on exit.

## Config layers

- Defaults: `config.DEFAULT_CONFIG`
- Global: `~/.config/0rb1t/config.json` (or `$XDG_CONFIG_HOME/0rb1t/config.json`)
- Project: `<cwd>/.0rb1t/config.json`

Merge order: defaults -> global -> project. `/config set` writes global config.

## Engine selection

- Config: `engine.name`, `engine.command`, `engine.auto`, `engine.model`, `engine.agent`
- Commands: `/engine` (status/capabilities), `/engine list`, `/engine use <name>`
- Switching engines goes through config + registry; core app code does not need engine-specific branches.

## Plugin model

Plugins are Python files with `register(api, ctx)`. They can register commands and hooks. Plugin errors are isolated and reported in `/plugins`.

## Extension points

- **New engine adapter**: implement `EngineAdapter`, declare capabilities honestly, register factory in `engines/registry.py`.
- **Commands**: builtins in `App._builtin_commands` or plugins via `api.register_command`.
- **Hooks**: `PluginManager.emit` / `api.register_hook`.
- **UI themes**: `ui.THEMES`.

## Known limitations

- Only OpenCode adapter is implemented. Registry supports adding more.
- OpenCode adapter currently declares conservative capabilities: `health`, `send`, `sessions.list`. Other capabilities are intentionally unsupported.
- TUI is custom ANSI/raw-mode based (no curses/Textual dependency); terminal compatibility depends on common ANSI/SGR mouse support.
- Plugins run in-process with no sandbox.
- Workflow engine, keybinding system, and full agent/profile management are foundational/incomplete.
