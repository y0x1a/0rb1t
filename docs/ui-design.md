# 0rb1t TUI design notes

## Language: "trace"

| Element | Treatment |
|---|---|
| **You** | A `▌` bar on the lifted `PANEL` surface. The *same* mark is the live input dock and the sent message band, so a message moves from dock to transcript. Slash-commands go quiet: `› /help`, no band. |
| **Assistant** | Directly on `BG`. A small `◦` + your configured name in lavender, body on the shared text column. Markdown-lite: `code`, **bold**, headings, bullets, quotes, rules, tinted code cards (no borders). |
| **Tools** | `● name  args` (dot: grey = neutral, violet = running, green = ok, red = error) + a dim `│` rail with up to 6 output lines and `… +N more lines`. |
| **Command output** | `· Title`, then structure inferred from shape: `/cmd` in soft accent, `key: value` with dim keys, `*` marks the active item. |
| **Thinking** | An orbiting comet (one braille cell, a dot circling the perimeter with a two-dot tail), drawn inline where the reply will land, with elapsed time. |
| **Dock** | Half-block top edge (no rule), soft-wrapped multiline, placeholder, command-mode colouring, `↑N` when scrolled. |
| **Chrome** | 1-row header (`◦ 0rb1t · <name>` … `cwd · session`), 1-row status (state left, key hints right, degrading by width). |
| **Empty state** | 3-row wordmark (pixel font compiled to half-blocks; the zero has a nucleus), tagline, four commands. Engine/model details are deliberately absent: `/engine`, `/model`, `/about`. |

Colour: two near-black surfaces only. `#6D28D9` is used for **marks** (bars, bullets, logo); accent *text* uses `ACCENT_SOFT` (`#9061F9`, >= 4.5:1 on both surfaces; enforced by tests).

## Module changes

- `brand.py` (new): wordmark (pixel bitmap -> half-blocks), tagline, comet frames.
- `theme.py`: new tokens (`PANEL`, `FAINT`, `TEXT_BRIGHT`, `CODE_BG`, `LAVENDER`...), and every theme `/theme` offers (`cyan green red amber pink mono`) now exists in the TUI. Previously they silently rendered as purple.
- `tui.py`: renderer rewrite (see contract notes).
- `cli.py`: persistent renderer, diffed painting, animation inputs, input-latency fix, `Ctrl+L`, scroll math delegated to the renderer, branded `--no-alt-screen`.
- `terminal.py`: cleanup also resets cursor shape and synchronized-output mode.
- `ui.py`: `LOGO` now comes from `brand` (legacy helpers otherwise untouched).
- Untouched: `input_editor.py`, `app.py`, `config.py`, `errors.py`, `integrations/`, engines, plugins, command dispatch, one-shot mode.

## Contract changes (all additive unless noted)

- `Message.status: str = ""`; `RenderState.add(role, content, status="")` (tool status).
- `RenderState.tick`, `RenderState.elapsed`: animation inputs set by the loop so frames stay a pure function of state.
- `TUIRenderer.frame(..., show_banner=True)`; new `build_transcript`, `max_scroll`, `render_header/status/dock/busy/markdown`.
- **Semantic change:** `render_transcript`/`format_message` `width` is now the full viewport width (was `cols - 2`). A full-bleed band can't be drawn into a pre-shrunk width; the renderer applies its own margins.
- `frame()` now emits absolutely-positioned rows with no `\033[2J`; the loop writes only when the frame changed (and clears once on resize).
- `ui.show_banner` is now honoured (it existed in config but was never read).
- `Ctrl+L` now repaints (was a no-op).

## Known limits

- Nothing in the handoff's engine path produces `tool` messages (the OpenCode adapter declares only `health/send/sessions.list`). The renderer styles them and is tested, but live tool rows need an adapter with the `stream` capability.
- In a wrapped input line, Up/Down still move between *logical* lines (editor semantics unchanged).
- Truecolor only (as before); no 256-colour or `NO_COLOR` fallback.
- No syntax highlighting inside code cards.
