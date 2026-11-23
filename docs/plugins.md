# Plugin Development

Plugins extend 0rb1t with commands and hooks. They are Python files loaded at startup.

## Plugin locations

- Global: `~/.config/0rb1t/plugins/*.py`
- Project: `<cwd>/.0rb1t/plugins/*.py`
- Extra paths: `plugins.paths` in config

## Minimal plugin

```py
from types import SimpleNamespace

def register(api, ctx):
    def hello(args, command_ctx):
        who = " ".join(args) if args else "world"
        return SimpleNamespace(
            ok=True,
            message=f"hello, {who}",
            clear=False,
            exit=False,
            new_session=False,
        )

    api.register_command("hello", hello, help="Say hello")
```

## API

`register(api, ctx)` receives:

- `api.register_command(name, handler, help="", aliases=[])`
- `api.register_hook(event, handler)`
- `api.log(message)`
- `ctx.app_version`, `ctx.config`, `ctx.data_dir`, `ctx.cwd`

Command handler signature: `handler(args: list[str], ctx: dict) -> CommandResult-like object`.

`CommandResult` fields used by core: `ok`, `message`, `clear`, `exit`, `new_session`.

## Hooks

Current hook names emitted by core include:

- `plugins.loaded`
- `command.before`, `command.after`
- `message.before`, `message.after`

Hook handlers receive a payload dict and should not raise; exceptions are isolated and reported.

## Engine-related extensions

For new engine adapters, use the engine registry in code (`engines/registry.py`) and follow the `EngineAdapter` capability contract. Do not fake unsupported capabilities; declare them as unsupported and raise normalized `EngineError`/`UnsupportedCapabilityError`.

## Safety notes

Plugins run in-process with your user permissions. Only install plugins you trust.
