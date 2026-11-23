"""Terminal UI for 0rb1t."""

from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
from typing import Any

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

# Shared neutrals
WHITE = "\033[38;2;245;240;255m"
GRAY = "\033[38;2;160;150;180m"
DIMGRAY = "\033[38;2;110;100;130m"
RED = "\033[38;2;255;110;140m"
GREEN = "\033[38;2;190;255;170m"

THEMES: dict[str, dict[str, str]] = {
    "purple": {
        "P1": "\033[38;2;210;170;255m",
        "P2": "\033[38;2;167;139;250m",
        "P3": "\033[38;2;139;92;246m",
        "P4": "\033[38;2;109;40;217m",
        "ACCENT": "\033[38;2;236;72;153m",
        "BAR": (109, 40, 217),
        "BAR2": (60, 20, 120),
    },
    "cyan": {
        "P1": "\033[38;2;180;255;255m",
        "P2": "\033[38;2;103;232;249m",
        "P3": "\033[38;2;34;211;238m",
        "P4": "\033[38;2;8;145;178m",
        "ACCENT": "\033[38;2;59;130;246m",
        "BAR": (8, 145, 178),
        "BAR2": (8, 80, 100),
    },
    "green": {
        "P1": "\033[38;2;200;255;210m",
        "P2": "\033[38;2;134;239;172m",
        "P3": "\033[38;2;74;222;128m",
        "P4": "\033[38;2;22;163;74m",
        "ACCENT": "\033[38;2;163;230;53m",
        "BAR": (22, 163, 74),
        "BAR2": (10, 90, 40),
    },
    "red": {
        "P1": "\033[38;2;255;200;200m",
        "P2": "\033[38;2;252;165;165m",
        "P3": "\033[38;2;248;113;113m",
        "P4": "\033[38;2;220;38;38m",
        "ACCENT": "\033[38;2;251;146;60m",
        "BAR": (220, 38, 38),
        "BAR2": (120, 20, 20),
    },
    "amber": {
        "P1": "\033[38;2;255;236;179m",
        "P2": "\033[38;2;252;211;77m",
        "P3": "\033[38;2;251;191;36m",
        "P4": "\033[38;2;217;119;6m",
        "ACCENT": "\033[38;2;251;146;60m",
        "BAR": (217, 119, 6),
        "BAR2": (120, 65, 5),
    },
    "pink": {
        "P1": "\033[38;2;255;210;235m",
        "P2": "\033[38;2;249;168;212m",
        "P3": "\033[38;2;244;114;182m",
        "P4": "\033[38;2;219;39;119m",
        "ACCENT": "\033[38;2;167;139;250m",
        "BAR": (219, 39, 119),
        "BAR2": (120, 20, 65),
    },
    "mono": {
        "P1": "\033[38;2;245;245;245m",
        "P2": "\033[38;2;212;212;212m",
        "P3": "\033[38;2;163;163;163m",
        "P4": "\033[38;2;115;115;115m",
        "ACCENT": "\033[38;2;255;255;255m",
        "BAR": (115, 115, 115),
        "BAR2": (64, 64, 64),
    },
}

# Active theme/module state
THEME_NAME = "purple"
APP_NAME = "0rb1t"
P1 = THEMES["purple"]["P1"]
P2 = THEMES["purple"]["P2"]
P3 = THEMES["purple"]["P3"]
P4 = THEMES["purple"]["P4"]
ACCENT = THEMES["purple"]["ACCENT"]
PINK = ACCENT  # back-compat alias
BAR_RGB = THEMES["purple"]["BAR"]
BAR2_RGB = THEMES["purple"]["BAR2"]

LOGO = r"""
███  ████  ████    █   █████   
█ ░░█ █░░░█ █░░░█  ██░   ░█░░░  
█░ ░█░████░░████░░  █░░   █░░░░ 
█░░ █░█░░█░ █░░░█ ░ █░░   █░░   
 ███ ░█░░░█░████░░ ███░   █░░   
  ░░░ ░░░  ░ ░░░░ ░ ░░░    ░░   
   ░░░  ░   ░ ░░░░   ░░░    ░
""".rstrip("\n")


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


COLOR = supports_color()


def c(text: str, *styles: str) -> str:
    if not COLOR or not styles:
        return text
    return "".join(styles) + text + RESET


def strip_ansi(text: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", text)


def width() -> int:
    return max(50, min(shutil.get_terminal_size((100, 28)).columns, 120))


def clear_screen() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def enter_alt_screen() -> None:
    from . import term

    term.enter_alt_screen()


def leave_alt_screen() -> None:
    from . import term

    term.leave_alt_screen()


def set_theme(name: str) -> bool:
    global THEME_NAME, P1, P2, P3, P4, ACCENT, PINK, BAR_RGB, BAR2_RGB
    key = name.lower().strip()
    if key not in THEMES:
        return False
    t = THEMES[key]
    THEME_NAME = key
    P1, P2, P3, P4 = t["P1"], t["P2"], t["P3"], t["P4"]
    ACCENT = t["ACCENT"]
    PINK = ACCENT
    BAR_RGB = t["BAR"]  # type: ignore[assignment]
    BAR2_RGB = t["BAR2"]  # type: ignore[assignment]
    return True


def set_name(name: str) -> None:
    global APP_NAME
    APP_NAME = name.strip() or "0rb1t"


def theme_names() -> list[str]:
    return list(THEMES.keys())


def banner(version: str, cwd: str, session_id: str | None = None) -> str:
    w = width()
    top = c("╭" + "─" * (w - 2) + "╮", P4)
    bottom = c("╰" + "─" * (w - 2) + "╯", P4)

    def row(content: str = "", visible_len: int | None = None) -> str:
        if visible_len is None:
            visible_len = len(strip_ansi(content))
        pad = max(0, w - 4 - visible_len)
        return c("│ ", P4) + content + " " * pad + c(" │", P4)

    logo_lines = LOGO.splitlines()
    colors = [P1, P2, P3, P3, P4, DIMGRAY, DIMGRAY]
    rows = [top, row()]
    for i, ln in enumerate(logo_lines):
        color = colors[min(i, len(colors) - 1)]
        rows.append(row(c(ln, color, BOLD), len(ln)))
    rows.append(row())
    subtitle = "terminal intelligence layer"
    rows.append(row(c(subtitle, WHITE, BOLD) + c("  //  ", DIMGRAY) + c(f"v{version}", P2),
                    len(subtitle) + 6 + len(f"v{version}")))
    cwd_show = cwd if len(cwd) <= w - 20 else "…" + cwd[-(w - 21):]
    sess = session_id[:12] + "…" if session_id and len(session_id) > 13 else (session_id or "new")
    meta = f"cwd {cwd_show}  •  session {sess}  •  theme {THEME_NAME}"
    rows.append(row(c(meta, GRAY), len(meta)))
    rows.append(row())
    cmds = "/help  /theme  /name  /new  /clear  /exit"
    rows.append(row(c("commands ", DIMGRAY) + c(cmds, P2), len("commands ") + len(cmds)))
    rows.append(bottom)
    return "\n".join(rows)


def render_screen_text(version: str, cwd: str, session_id: str | None = None) -> str:
    return banner(version, cwd, session_id)


def prompt_text() -> str:
    return c("╭─", P4) + c(" you", P1, BOLD) + "\n" + c("╰─", P4) + c("› ", P3, BOLD)


def assistant_label() -> str:
    return c("╭─", P4) + c(f" {APP_NAME}", P2, BOLD) + c(" ◆", ACCENT)


def assistant_cont() -> str:
    return c("│ ", P4)


def assistant_end() -> str:
    return c("╰─", P4) + c("◆", DIMGRAY)


def system(text: str) -> str:
    return c("  ◇ ", P3) + c(text, GRAY)


def error(text: str) -> str:
    return c("  ✖ ", RED) + c(text, RED)


def success(text: str) -> str:
    return c("  ✔ ", GREEN) + c(text, GRAY)
