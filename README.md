# 0rb1t

`0rb1t` is a customizable terminal intelligence environment. It provides its own CLI, config system, command/runtime layer, and extension points; engines are pluggable adapters underneath.

[OpenCode](https://opencode.ai) is the **first supported engine adapter**. 0rb1t is designed so engine-specific behavior stays isolated in `engines/`, while the product surface (UI, config, commands, plugins, profiles, context) belongs to 0rb1t.

> Status: early but functional. Core REPL, engine adapter boundary, OpenCode adapter, config migration, themes, and a basic plugin system work today. Larger ecosystem features (workflow engine, full agent/profile management, sandboxed plugins, additional engine adapters) are staged.

## What works now

- **Terminal TUI REPL** - scrollable transcript viewport + fixed input dock; input stays fixed while conversation scrolls
- **Input editor** - prompt decoration is non-editable; Enter submits, Shift+Enter inserts newline; arrow/home/end/Ctrl+A/E/K/U editing; paste and escape-sequence filtering
- **Scrolling behavior** - mouse wheel and keyboard scrolling; auto-follows latest message, pauses on manual scroll-up, resumes at bottom
- **Engine-backed chat** - session continuity handled by active engine adapter (OpenCode first)
- **One-shot mode** - `0rb1t "message"` or `0rb1t --once "message"`
- **Configurable UI** - dark purple identity, themes, display name, alt-screen/banner toggles
- **Config system** - defaults + global + project config, validation, migration, dotted `get/set`
- **Engine capability system** - adapters declare supported capabilities; core checks them explicitly
- **Profiles/plugins/context** - profile records, local Python plugins, global/project key-value context
- **Optional Discord Rich Presence** - configurable, graceful when Discord unavailable

## Install

Requirements:
- Python 3.10+
- An engine adapter's dependencies. For the default OpenCode adapter: `opencode` on `PATH`

```bash
cd ~/0rb1t
python3 -m ensurepip --upgrade --user   # if needed
python3 -m pip install --user -e .
export PATH="$HOME/.local/bin:$PATH"
0rb1t
```

## Usage

Interactive:

```bash
0rb1t
```

One-shot:

```bash
0rb1t "summarize this repo"
0rb1t --once "explain this error" --session <session-id>
```

Useful flags:

- `--cwd <dir>` - run engine/session in a specific directory
- `--no-alt-screen` - run inline instead of full-screen alternate terminal

## Built-in commands

| Command | Description |
|---|---|
| `/help` | List commands |
| `/theme [name]` | List or switch themes |
| `/name <name>` | Set assistant display name |
| `/config [path|get|set|reset]` | Inspect/edit global config |
| `/profile [list|use|add]` | Manage profile records |
| `/engine` | Show active engine, health, capabilities, available adapters |
| `/engine list` | List available engine adapters |
| `/engine use <name>` | Switch active engine (saved to global config) |
| `/plugins` | List loaded plugins and errors |
| `/context <global|project> ...` | Manage persistent context key-values |
| `/session` | Show current session id |
| `/new` | Start a fresh session |
| `/clear` | Clear screen |
| `/version` | Show version |
| `/exit` | Quit |

## Configuration

- Global: `~/.config/0rb1t/config.json` (or `$XDG_CONFIG_HOME/0rb1t/config.json`)
- Project: `<cwd>/.0rb1t/config.json`

Merge order: `defaults <- global <- project`.

Examples:

```text
/config set ui.theme cyan
/config set ui.name Nova
/config set ui.alt_screen false
/config set engine.model "provider/model"
/config set integrations.discord.enabled true
/config set integrations.discord.client_id "<discord-app-id>"
/config set integrations.discord.large_image "orb1t"
/config get engine.command
/config path
```

### Discord Rich Presence

Discord integration is optional and disabled by default. If enabled, 0rb1t updates presence on startup and when `/name` or Discord config changes, and clears it on exit. If Discord is not running or IPC fails, 0rb1t continues normally.

- Create a Discord application at the Discord Developer Portal.
- Copy the Application ID into `integrations.discord.client_id`.
- Upload a Rich Presence art asset (e.g. `orb1t`) and set `integrations.discord.large_image`.
- Presence details: `Talking to {AI_NAME}` (from `ui.name`).
- Presence state: `AI-powered development environment`.
- Button: `GitHub` -> `https://github.com/y0x1a/0rb1t`.

See [docs/configuration.md](docs/configuration.md).

## Plugins

Plugins are Python files with a `register(api, ctx)` function.

Locations:
- `~/.config/0rb1t/plugins/*.py`
- `<cwd>/.0rb1t/plugins/*.py`
- extra paths in `plugins.paths`

Example: [examples/plugins/hello_plugin.py](examples/plugins/hello_plugin.py). See [docs/plugins.md](docs/plugins.md).

## Architecture

See [docs/architecture.md](docs/architecture.md) for module boundaries, runtime flow, and extension points.

## Development

```bash
python3 -m pip install -e .[dev]
PYTHONPATH=src pytest -q
python3 -m py_compile src/orb1t/*.py src/orb1t/engines/*.py src/orb1t/plugins/*.py
```

## Project docs

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Plugins](docs/plugins.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT - see [LICENSE](LICENSE).
