# Configuration Reference

## Locations

- Global: `~/.config/0rb1t/config.json` (or `$XDG_CONFIG_HOME/0rb1t/config.json`)
- Project: `<project>/.0rb1t/config.json`

Project config overrides global config, which overrides defaults.

## Default shape

```json
{
  "version": 1,
  "engine": {
    "name": "opencode",
    "command": "opencode",
    "auto": true,
    "model": null,
    "agent": null
  },
  "ui": {
    "theme": "purple",
    "name": "0rb1t",
    "alt_screen": true,
    "show_banner": true
  },
  "integrations": {
    "discord": {
      "enabled": false,
      "client_id": "",
      "large_image": "orb1t",
      "large_text": "0rb1t"
    }
  },
  "persona": {
    "prompt": "..."
  },
  "commands": {
    "aliases": {
      "q": "exit",
      "h": "help",
      "?": "help"
    }
  },
  "plugins": {
    "enabled": true,
    "paths": []
  },
  "profiles": {
    "active": "default",
    "items": {
      "default": {
        "name": "default",
        "engine": {},
        "persona_prompt": null
      }
    }
  }
}
```

## Engine config

- `engine.name` - active adapter name (default `opencode`)
- `engine.command` - engine executable/command for adapters that use one
- `engine.auto` - adapter-specific auto-approval/automation flag (OpenCode: passes `--auto`)
- `engine.model` - optional model id passed to adapters that support it
- `engine.agent` - optional agent name passed to adapters that support it

Switch engines via config or command:

```text
/engine list
/engine use opencode
/config get engine.name
```

## CLI/REPL commands

- `/config` - summary
- `/config path` - show global/project paths
- `/config get <dotted.key>` - read value
- `/config set <dotted.key> <value>` - set global value (JSON or scalar)
- `/config reset` - reset global config to defaults
- `/engine` - active engine, health, capabilities, available adapters
- `/engine list` - list adapters
- `/engine use <name>` - switch active engine

Examples:

```text
/config set ui.theme cyan
/config set ui.alt_screen false
/config set engine.model "provider/model"
/config set engine.name opencode
```

## Discord integration

`integrations.discord` config:

- `enabled` - enable Discord Rich Presence (default `false`)
- `client_id` - Discord application ID
- `large_image` - Discord asset key for the large image
- `large_text` - hover text for the large image

Behavior:
- Updates on startup and when AI name/config changes (`/name`, `/config set ui.name ...`, or Discord config changes).
- Details: `Talking to {AI_NAME}` where `{AI_NAME}` is `ui.name`.
- State: `AI-powered development environment`.
- Button: `GitHub` -> `https://github.com/y0x1a/0rb1t`.
- Clears presence on exit. Connection failures and missing Discord are ignored.

## Migration

Legacy v0.1 config with top-level `theme` and `name` is migrated to `ui.theme` and `ui.name`.
