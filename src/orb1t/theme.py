"""Theme helpers for the 0rb1t TUI.

Design rules encoded here:

* Two near-black surfaces only: ``BG`` (transcript) and ``PANEL`` (you: the
  input dock and your messages).  Hierarchy comes from type, not boxes.
* ``ACCENT`` (#6D28D9) is reserved for *marks*: rails, bullets, the logo.
  It is only ~3:1 against ``BG``, so accent *text* uses ``ACCENT_SOFT``.
* Neutrals are cool and slightly desaturated so the purple reads as the only
  colour in the room.
"""

from __future__ import annotations

from dataclasses import dataclass


def hex_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def fg(hex_color: str) -> str:
    r, g, b = hex_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m"


def bg(hex_color: str) -> str:
    r, g, b = hex_rgb(hex_color)
    return f"\033[48;2;{r};{g};{b}m"


@dataclass(frozen=True)
class Theme:
    name: str
    # Identity ---------------------------------------------------------
    ACCENT: str = "#6D28D9"       # primary purple: marks only
    ACCENT_SOFT: str = "#9061F9"  # accent text / highlights (>=4.5:1 on BG and PANEL)
    ACCENT_DIM: str = "#4C1D95"   # quiet marks, gradients
    LAVENDER: str = "#C4B5FD"     # the assistant's name
    # Surfaces ---------------------------------------------------------
    BG: str = "#0B0B10"           # near-black
    PANEL: str = "#15151D"        # you: dock + your messages
    PANEL_ALT: str = "#1B1B26"
    CODE_BG: str = "#101017"      # code blocks sit just above BG
    # Text -------------------------------------------------------------
    TEXT_BRIGHT: str = "#F4F4F5"  # headings, emphasis
    TEXT: str = "#D4D4D8"         # body
    MUTED: str = "#A1A1AA"
    DIM: str = "#71717A"
    FAINT: str = "#3F3F4A"        # rails, rules
    CODE: str = "#C4B5FD"         # inline code
    # Semantic ---------------------------------------------------------
    ERROR: str = "#FB7185"
    SUCCESS: str = "#86EFAC"
    WARNING: str = "#FBBF24"
    APP_NAME: str = "0rb1t"       # the user's configured AI name

    # Legacy aliases used by older code/tests ---------------------------
    USER: str = "#C4B5FD"
    ASSISTANT: str = "#DDD6FE"
    P1: str = "#E9D5FF"
    P2: str = "#C4B5FD"
    P3: str = "#8B5CF6"
    GRAY: str = "#9CA3AF"
    RED: str = "#FB7185"
    GREEN: str = "#86EFAC"

    def style(
        self,
        text: str,
        *,
        fg: str | None = None,
        bg: str | None = None,
        bold: bool = False,
        dim: bool = False,
        italic: bool = False,
    ) -> str:
        parts: list[str] = []
        if bold:
            parts.append("\033[1m")
        if dim:
            parts.append("\033[2m")
        if italic:
            parts.append("\033[3m")
        if fg:
            parts.append(globals()["fg"](fg))
        if bg:
            parts.append(globals()["bg"](bg))
        if not parts:
            return text
        return "".join(parts) + text + "\033[0m"


# name -> (accent, accent_soft, accent_dim, lavender).  Names mirror
# ``ui.THEMES`` (what ``/theme`` lists), so every theme the command accepts
# is a theme the TUI can actually draw.
_VARIANTS: dict[str, tuple[str, str, str, str]] = {
    "purple": ("#6D28D9", "#9061F9", "#4C1D95", "#C4B5FD"),
    "cyan": ("#0891B2", "#22D3EE", "#0E4F63", "#67E8F9"),
    "green": ("#16A34A", "#4ADE80", "#14532D", "#86EFAC"),
    "red": ("#DC2626", "#F87171", "#7F1D1D", "#FCA5A5"),
    "amber": ("#D97706", "#FBBF24", "#78350F", "#FCD34D"),
    "pink": ("#DB2777", "#F472B6", "#831843", "#F9A8D4"),
    "mono": ("#737373", "#A3A3A3", "#404040", "#D4D4D4"),
}


def _make(name: str, accent: str, soft: str, dim: str, lav: str) -> Theme:
    return Theme(
        name=name,
        ACCENT=accent,
        ACCENT_SOFT=soft,
        ACCENT_DIM=dim,
        LAVENDER=lav,
        CODE=lav,
        USER=lav,
        P2=lav,
        P3=soft,
    )


THEMES: dict[str, Theme] = {k: _make(k, *v) for k, v in _VARIANTS.items()}
THEMES["dark"] = Theme(name="dark")  # historical alias of the default look


def get_theme(name: str, app_name: str = "0rb1t") -> Theme:
    base = THEMES.get((name or "purple").lower().strip(), THEMES["purple"])
    return Theme(**{**base.__dict__, "APP_NAME": app_name or "0rb1t", "name": base.name})
