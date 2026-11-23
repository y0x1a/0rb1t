# 0rb1t

`0rb1t` is a customizable terminal intelligence environment. It provides its own CLI, configuration system, command/runtime layer, and extension points, with AI engines running underneath as pluggable adapters.

[OpenCode](https://opencode.ai) is the **first supported engine adapter**. Engine-specific behavior stays isolated inside `engines/`, while the product experience (UI, configuration, commands, plugins, profiles, and context) belongs to 0rb1t.

> **Status:** Early but functional. The core REPL, engine adapter boundary, OpenCode adapter, configuration migration, themes, and basic plugin system are working. Larger ecosystem features are staged for future releases.

## What works now

- **Terminal TUI REPL** - Scrollable transcript viewport with a fixed input dock.
- **Input editor** - Non-editable prompt decoration, Enter to submit, Shift+Enter for newlines, keyboard editing, paste support, and escape-sequence filtering.
- **Scrolling behavior** - Mouse wheel and keyboard scrolling, automatic follow mode, and manual scroll control.
- **Engine-backed chat** - Session continuity handled by the active engine adapter.
- **One-shot mode** - `0rb1t "message"` or `0rb1t --once "message"`.
- **Configurable UI** - Dark purple identity, themes, display name, alternate-screen and banner controls.
- **Configuration system** - Defaults, global and project configuration, validation, migration, and dotted `get/set` operations.
- **Engine capabilities** - Adapters declare supported capabilities, which the core checks explicitly.
- **Profiles, plugins, and context** - Profile records, local Python plugins, and global/project key-value context.
- **Optional Discord Rich Presence** - Configurable integration with graceful fallback when Discord is unavailable.

## Installation

### Requirements

- Python 3.10 or newer.
- [pipx](https://pipx.pypa.io/stable/).
- An installed engine adapter and its dependencies.

For the default OpenCode adapter, [OpenCode](https://opencode.ai) must be installed and available on your `PATH`.

### Install with pipx

```bash
pipx install 0xrb1t
```

Launch 0rb1t:

```bash
0rb1t
```

Check the installed version:

```bash
0rb1t --version
```

To upgrade:

```bash
pipx upgrade 0xrb1t
```

## Usage

### Interactive mode

```bash
0rb1t
```

### One-shot mode

```bash
0rb1t "summarize this repo"
0rb1t --once "explain this error"
0rb1t --once "continue this task" --session <session-id>
```

### Useful flags

| Flag | Description |
|---|---|
| `--version` | Show the installed version |
| `--cwd <dir>` | Set the working directory for the engine/session |
| `--no-alt-screen` | Run inline instead of using the terminal alternate screen |
| `--once <message>` | Send a message and print the response |
| `--session <session-id>` | Specify a session for one-shot mode |

## Built-in commands

| Command | Description |
|---|---|
| `/help` | List available commands |
| `/theme [name]` | List or switch themes |
| `/name <name>` | Set the assistant display name |
| `/config [path|get|set|reset]` | Inspect or edit global configuration |
| `/profile [list\|use\|add]` | Manage profile records |
| `/engine` | Show active engine, health, capabilities, and available adapters |
| `/engine list` | List available engine adapters |
| `/engine use <name>` | Switch the active engine |
| `/model` | Show the active/configured model |
| `/about` | Show environment details |
| `/discord [status\|reconnect\|enable\|disable]` | Control Discord Rich Presence |
| `/plugins` | List loaded plugins and errors |
| `/context <global\|project> ...` | Manage persistent context key-values |
| `/session` | Show the current session ID |
| `/new` | Start a fresh session |
| `/clear` | Clear the screen |
| `/version` | Show the version |
| `/exit` | Quit |

## Configuration

Configuration files:

- **Global:** `~/.config/0rb1t/config.json` (or `$XDG_CONFIG_HOME/0rb1t/config.json`)
- **Project:** `<cwd>/.0rb1t/config.json`

Configuration is merged in this order:

```text
defaults <- global <- project
```

### Examples

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

## Discord Rich Presence

Discord integration is optional and disabled by default.

When enabled, 0rb1t updates presence on startup, refreshes it every minute, and updates it when `/name` or Discord configuration changes. Presence is cleared on exit.

If Discord is unavailable or IPC fails, 0rb1t continues normally.

To configure it:

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Copy its Application ID into `integrations.discord.client_id`.
3. Upload a Rich Presence art asset (for example, `orb1t`).
4. Set `integrations.discord.large_image` to the asset name.

Presence details rotate through phrases such as `Building with 0rb1t`, `Shipping with 0rb1t`, `Coding with 0rb1t`, and `Debugging with 0rb1t`.

Presence state: `github.com/y0x1a/0rb1t`.

See [docs/configuration.md](docs/configuration.md).

## Plugins

Plugins are Python files containing a `register(api, ctx)` function.

Plugin locations:

- `~/.config/0rb1t/plugins/*.py`
- `<cwd>/.0rb1t/plugins/*.py`
- Additional paths configured through `plugins.paths`.

Example: [examples/plugins/hello_plugin.py](examples/plugins/hello_plugin.py).

See [docs/plugins.md](docs/plugins.md).

## Architecture

0rb1t separates the product experience from the underlying AI engine.

The engine adapter boundary allows different engines to be integrated without coupling engine-specific behavior to the core application.

See [docs/architecture.md](docs/architecture.md) for module boundaries, runtime flow, and extension points.

## Development

Clone the repository:

```bash
git clone https://github.com/y0x1a/0rb1t.git
cd 0rb1t
```

Install development dependencies:

```bash
python3 -m pip install -e ".[dev]"
```

Run tests:

```bash
PYTHONPATH=src pytest -q
```

Run compilation checks:

```bash
python3 -m py_compile src/orb1t/*.py src/orb1t/engines/*.py src/orb1t/plugins/*.py
```

## Project documentation

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Plugins](docs/plugins.md)
- [Contributing](CONTRIBUTING.md)

## Links

- **PyPI:** https://pypi.org/project/0xrb1t/
- **GitHub:** https://github.com/y0x1a/0rb1t
- **Issues:** https://github.com/y0x1a/0rb1t/issues

## License

MIT. See [LICENSE](LICENSE).