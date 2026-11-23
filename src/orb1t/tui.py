"""Viewport-based TUI renderer for 0rb1t."""

from __future__ import annotations

import re
import shutil
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Iterable

from .input_editor import InputBuffer


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def visible_len(text: str) -> int:
    return len(strip_ansi(text))


def pad_ansi(text: str, width: int) -> str:
    vl = visible_len(text)
    if vl >= width:
        return truncate_ansi(text, width)
    return text + (" " * (width - vl))


def truncate_ansi(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if visible_len(text) <= width:
        return text
    out: list[str] = []
    vis = 0
    i = 0
    while i < len(text) and vis < width:
        ch = text[i]
        if ch == "\x1b":
            m = ANSI_RE.match(text, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
        out.append(ch)
        vis += 1
        i += 1
    out.append("\033[0m")
    return "".join(out)


@dataclass
class Message:
    role: str  # user|assistant|system|error|tool|status
    content: str


@dataclass
class RenderState:
    messages: list[Message] = field(default_factory=list)
    scroll: int = 0
    follow: bool = True
    status: str = ""
    busy: bool = False
    busy_label: str = ""

    def add(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=str(content)))

    def clear_messages(self) -> None:
        self.messages.clear()
        self.scroll = 0
        self.follow = True


class TUIRenderer:
    def __init__(self, theme) -> None:
        self.theme = theme

    def wrap_text(self, text: str, width: int) -> list[str]:
        width = max(1, width)
        out: list[str] = []
        for raw in text.splitlines() or [""]:
            if raw == "":
                out.append("")
                continue
            # preserve leading spaces modestly
            indent = len(raw) - len(raw.lstrip(" "))
            body = raw[indent:]
            avail = max(1, width - indent)
            chunks = textwrap.wrap(
                body,
                width=avail,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]
            for c in chunks:
                out.append((" " * indent) + c)
        return out

    def format_message(self, msg: Message, width: int) -> list[str]:
        t = self.theme
        inner = max(10, width)
        lines: list[str] = []
        if msg.role == "user":
            label = t.style("you", fg=t.USER, bold=True)
            body_lines = self.wrap_text(msg.content, max(1, inner - 6))
            lines.append(label)
            for bl in body_lines:
                lines.append(t.style("  ", fg=t.DIM) + t.style(bl, fg=t.TEXT))
            lines.append("")
        elif msg.role == "assistant":
            label = t.style(t.APP_NAME, fg=t.ASSISTANT, bold=True) + t.style("  ", fg=t.DIM) + t.style("◆", fg=t.ACCENT)
            body_lines = self.wrap_text(msg.content, max(1, inner - 4))
            lines.append(label)
            for bl in body_lines:
                lines.append(t.style("  ", fg=t.DIM) + t.style(bl, fg=t.TEXT))
            lines.append("")
        elif msg.role == "error":
            for i, bl in enumerate(self.wrap_text(msg.content, max(1, inner - 4))):
                mark = t.style("! ", fg=t.ERROR, bold=True) if i == 0 else "  "
                lines.append(mark + t.style(bl, fg=t.ERROR))
            lines.append("")
        elif msg.role in ("system", "tool", "status"):
            mark = "◆" if msg.role == "system" else "▸"
            color = t.MUTED if msg.role != "tool" else t.ACCENT_SOFT
            for i, bl in enumerate(self.wrap_text(msg.content, max(1, inner - 4))):
                p = t.style(f"{mark} ", fg=t.ACCENT) if i == 0 else "  "
                lines.append(p + t.style(bl, fg=color))
            if msg.role != "status":
                lines.append("")
        else:
            lines.extend(self.wrap_text(msg.content, inner))
            lines.append("")
        return lines

    LOGO = [
        "███  ████  ████    █   █████   ",
        "█ ░░█ █░░░█ █░░░█  ██░   ░█░░░  ",
        "█░ ░█░████░░████░░  █░░   █░░░░ ",
        "█░░ █░█░░█░ █░░░█ ░ █░░   █░░   ",
        " ███ ░█░░░█░████░░ ███░   █░░   ",
        "  ░░░ ░░░  ░ ░░░░ ░ ░░░    ░░   ",
        "   ░░░  ░   ░ ░░░░   ░░░    ░  ",
    ]
    LOGO_COMPACT = [
        " █▀█ █▀▄ █▀▄ ▄█ ▀█▀",
        " █▄█ █▀▄ █▀▄  █  █ ",
        " ▀▀▀ ▀ ▀ ▀▀▀  ▀  ▀ ",
    ]

    def render_welcome(self, width: int, version: str, engine_name: str = "") -> list[str]:
        _ = engine_name  # intentionally not shown in main UI
        t = self.theme
        w = max(20, width)
        lines: list[str] = []
        lines.append("")
        use_full = w >= 72
        use_compact = w >= 34
        if use_full:
            colors = [t.ACCENT_SOFT, t.ACCENT, t.ACCENT, t.ACCENT_DIM, t.ACCENT_DIM, t.DIM, t.DIM]
            for i, row in enumerate(self.LOGO):
                color = colors[i] if i < len(colors) else t.ACCENT
                lines.append(t.style(row.rstrip(), fg=color, bold=(i < 3)))
        elif use_compact:
            for i, row in enumerate(self.LOGO_COMPACT):
                lines.append(t.style(row, fg=t.ACCENT if i < 2 else t.ACCENT_DIM, bold=(i == 0)))
        else:
            lines.append(t.style("0rb1t", fg=t.ACCENT, bold=True))

        lines.append("")
        lines.append(t.style("terminal intelligence environment", fg=t.MUTED))
        lines.append(t.style(f"v{version}", fg=t.DIM))
        lines.append("")
        lines.append(t.style("Get started", fg=t.TEXT, bold=True))
        for cmd, desc in [
            ("/help", "commands and shortcuts"),
            ("/name", "set assistant identity"),
            ("/engine", "engine status"),
            ("/about", "environment details"),
        ]:
            lines.append(t.style(f"  {cmd:<8}", fg=t.ACCENT_SOFT, bold=True) + t.style(desc, fg=t.MUTED))
        lines.append("")
        lines.append(t.style("Type a message to begin.", fg=t.DIM))
        return lines

    def render_transcript(self, messages: list[Message], width: int, *, version: str = "", engine_name: str = "") -> list[str]:
        if not messages:
            return self.render_welcome(width, version, engine_name)
        lines: list[str] = []
        for msg in messages:
            lines.extend(self.format_message(msg, width))
        if not lines:
            return self.render_welcome(width, version, engine_name)
        return lines

    def layout(self, cols: int, rows: int, ibuf: InputBuffer) -> dict:
        # Reserve: header 1, sep 1, status 1, input min 1 + prompt line
        header_h = 1
        status_h = 1
        sep_h = 1
        min_viewport = 3
        min_input = 3  # prompt + 1 line + bottom padding feel via sep
        # compute input height from buffer
        input_lines = max(1, len(ibuf.lines))
        max_input = max(1, rows - header_h - sep_h - status_h - min_viewport)
        input_h = min(input_lines, max_input)
        viewport_h = rows - header_h - sep_h - input_h - status_h
        if viewport_h < 1:
            viewport_h = 1
            input_h = max(1, rows - header_h - sep_h - status_h - viewport_h)
        return {
            "header": header_h,
            "viewport": viewport_h,
            "sep": sep_h,
            "input": input_h,
            "status": status_h,
        }

    def frame(
        self,
        *,
        cols: int,
        rows: int,
        state: RenderState,
        ibuf: InputBuffer,
        version: str,
        cwd: str,
        session_id: str | None,
        engine_name: str,
    ) -> tuple[str, tuple[int, int], bool]:
        t = self.theme
        layout = self.layout(cols, rows, ibuf)
        transcript = self.render_transcript(state.messages, max(10, cols - 2), version=version, engine_name=engine_name)
        vp_h = layout["viewport"]
        max_scroll = max(0, len(transcript) - vp_h)
        if state.follow:
            state.scroll = max_scroll
        else:
            state.scroll = max(0, min(state.scroll, max_scroll))
        visible = transcript[state.scroll : state.scroll + vp_h]
        while len(visible) < vp_h:
            visible.append("")

        def paint(line: str, bg: str = t.BG) -> str:
            return t.style(pad_ansi(line, cols), bg=bg)

        out: list[str] = []
        out.append("\033[H\033[2J")  # home + clear; prevents stale frame artifacts
        # header - 0rb1t identity, not engine implementation
        name = t.APP_NAME
        left = " " + t.style("0rb1t", fg=t.TEXT, bold=True)
        if name.strip().lower() != "0rb1t":
            left += t.style(" / ", fg=t.DIM) + t.style(name, fg=t.ACCENT_SOFT, bold=True)
        sess = session_id[:8] + "…" if session_id and len(session_id) > 9 else "new session"
        right = t.style(sess, fg=t.MUTED) + " "
        gap = cols - visible_len(left) - visible_len(right)
        header = left + (" " * max(1, gap)) + right
        out.append(paint(header, t.BG) + "\r\n")

        # viewport
        for ln in visible:
            line = " " + ln if ln else ""
            out.append(paint(line, t.BG) + "\r\n")

        # subtle separator above input dock
        sep = " " + t.style("─" * max(0, cols - 2), fg=t.ACCENT_DIM)
        out.append(paint(sep, t.BG) + "\r\n")

        # input
        input_h = layout["input"]
        total_il = len(ibuf.lines)
        start = 0
        if total_il > input_h:
            start = min(max(0, ibuf.row - input_h + 1), total_il - input_h)
        for i in range(input_h):
            li = start + i
            content = ibuf.lines[li] if li < total_il else ""
            if i == 0 and start == 0:
                pfx = " " + t.style("›", fg=t.ACCENT, bold=True) + " "
                pfx_len = 3
            else:
                pfx = "   "
                pfx_len = 3
            avail = max(1, cols - pfx_len)
            line_col = ibuf.col if li == ibuf.row else 0
            hstart = 0
            if len(content) > avail - 1:
                hstart = max(0, line_col - avail + 2)
                content_disp = content[hstart : hstart + avail]
            else:
                content_disp = content
            line = pfx + t.style(content_disp, fg=t.TEXT)
            out.append(paint(line, t.BG) + "\r\n")

        # subtle status bar
        if state.busy:
            st = " " + t.style("●", fg=t.ACCENT, bold=True) + " " + t.style(state.busy_label or "thinking", fg=t.MUTED)
        else:
            st = " " + t.style("◆", fg=t.ACCENT_DIM) + " " + t.style(state.status or "ready", fg=t.DIM)
        hints = "enter send  ·  shift+enter newline  ·  /help"
        if cols < 62:
            hints = "enter send  ·  /help"
        if cols < 32:
            hints = "/help"
        right_st = t.style(hints, fg=t.DIM) + " "
        gap = cols - visible_len(st) - visible_len(right_st)
        status = st + (" " * max(1, gap)) + right_st
        out.append(paint(status, t.BG))

        # cursor position
        cur_row_in_input = ibuf.row - start
        cur_row_in_input = max(0, min(input_h - 1, cur_row_in_input))
        screen_row = 1 + layout["header"] + layout["viewport"] + layout["sep"] + cur_row_in_input
        # compute horizontal cursor
        line_content = ibuf.lines[ibuf.row] if ibuf.row < len(ibuf.lines) else ""
        avail = max(1, cols - 4)
        hstart = 0
        if len(line_content) > avail - 1:
            hstart = max(0, ibuf.col - avail + 2)
        screen_col = 1 + 3 + (ibuf.col - hstart)
        screen_col = max(1, min(cols, screen_col))
        return "".join(out), (screen_row, screen_col), max_scroll > 0
