"""Theme helpers for 0rb1t TUI."""

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
    # Identity
    ACCENT: str = "#6D28D9"  # primary purple
    ACCENT_SOFT: str = "#8B5CF6"
    ACCENT_DIM: str = "#4C1D95"
    # Backgrounds / surfaces
    BG: str = "#0B0B10"       # deep near-black
    PANEL: str = "#111118"    # input/status subtle lift
    PANEL_ALT: str = "#161622"
    # Text
    TEXT: str = "#F3F4F6"
    MUTED: str = "#A1A1AA"
    DIM: str = "#6B7280"
    # Semantic
    USER: str = "#C4B5FD"
    ASSISTANT: str = "#DDD6FE"
    ERROR: str = "#FB7185"
    SUCCESS: str = "#86EFAC"
    WARNING: str = "#FBBF24"
    APP_NAME: str = "0rb1t"

    # Legacy aliases used by older code/tests
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


THEMES = {
    "purple": Theme(name="purple"),
    "dark": Theme(name="dark"),
}


def get_theme(name: str, app_name: str = "0rb1t") -> Theme:
    base = THEMES.get((name or "purple").lower().strip(), THEMES["purple"])
    return Theme(**{**base.__dict__, "APP_NAME": app_name, "name": base.name})
