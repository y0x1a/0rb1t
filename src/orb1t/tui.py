"""Viewport-based TUI renderer for 0rb1t.

Visual language ("trace")
-------------------------
* One vertical bar ``▌`` is the mark for *your* voice.  It appears in the live
  input dock and again in the sent message band, so a message visibly moves
  from the dock into the transcript.
* Two near-black surfaces: ``BG`` for the transcript, ``PANEL`` for you.  The
  assistant speaks directly on ``BG``; hierarchy comes from type, not boxes.
* A single text column (``GUTTER``) shared by every role keeps the eye on one
  vertical line.
* While the engine works, an orbiting comet is drawn inline where the reply
  will land.

Contract notes
--------------
Public names from the previous renderer are preserved (``Message``,
``RenderState``, ``TUIRenderer.frame/layout/render_transcript/format_message/
render_welcome/wrap_text``, ``strip_ansi``, ``visible_len``, ``pad_ansi``,
``truncate_ansi``).  Additions are optional and defaulted.  One semantic
change: the ``width`` passed to ``render_transcript``/``format_message`` is now
the *full viewport width* (previously ``cols - 2``), because full-bleed bands
cannot be drawn into a pre-shrunk width.  The renderer applies its own margins.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field

from . import brand
from .input_editor import InputBuffer
from .theme import bg as _bg_seq

# --------------------------------------------------------------------------
# Text primitives (display-width aware)
# --------------------------------------------------------------------------

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?")
_CSI_FULL_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ESC2_RE = re.compile(r"\x1b[@-Z\\-_]")
# every C0/C1 control except TAB (0x09) and LF (0x0a)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

_ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF}


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def char_width(ch: str) -> int:
    """Terminal cell width of one character (0, 1 or 2)."""
    o = ord(ch)
    if o < 0x20 or 0x7F <= o < 0xA0:
        return 0
    if o < 0x7F:
        return 1
    if o in _ZERO_WIDTH or 0xFE00 <= o <= 0xFE0F or unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def text_width(text: str) -> int:
    if text.isascii():
        return len(text)
    return sum(char_width(c) for c in text)


def visible_len(text: str) -> int:
    return text_width(strip_ansi(text))


def truncate_ansi(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if visible_len(text) <= width:
        return text
    out: list[str] = []
    vis = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\x1b":
            m = ANSI_RE.match(text, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
        cw = char_width(ch)
        if vis + cw > width:
            break
        out.append(ch)
        vis += cw
        i += 1
    out.append("\033[0m")
    return "".join(out)


def pad_ansi(text: str, width: int) -> str:
    vl = visible_len(text)
    if vl >= width:
        return truncate_ansi(text, width)
    return text + (" " * (width - vl))


def clip(text: str, width: int, ellipsis: str = "…") -> str:
    """Clip *plain* text to ``width`` cells, ending with an ellipsis."""
    if width <= 0:
        return ""
    if text_width(text) <= width:
        return text
    keep = max(0, width - text_width(ellipsis))
    out, w = [], 0
    for ch in text:
        cw = char_width(ch)
        if w + cw > keep:
            break
        out.append(ch)
        w += cw
    return "".join(out) + (ellipsis if width >= text_width(ellipsis) else "")


def sanitize(text: str) -> str:
    """Make arbitrary engine output safe to draw.

    Engine/tool output may contain colour codes, OSC titles, carriage returns
    or stray control bytes.  Drawn raw they corrupt the screen, so we drop
    them and expand tabs.
    """
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    text = _OSC_RE.sub("", text)
    text = _CSI_FULL_RE.sub("", text)
    text = _ESC2_RE.sub("", text)
    text = _CTRL_RE.sub("", text)
    if "\t" in text:
        text = "\n".join(line.expandtabs(4) for line in text.split("\n"))
    return text


def wrap_spans(text: str, width: int) -> list[tuple[int, int]]:
    """Greedy word wrap returning ``(start, end)`` index spans into ``text``.

    Returning spans (not strings) lets callers keep per-character styling
    aligned while wrapping.  Words longer than ``width`` are hard-broken.
    """
    width = max(1, width)
    n = len(text)
    if n == 0:
        return [(0, 0)]
    spans: list[tuple[int, int]] = []
    start = 0
    w = 0
    brk = -1
    i = 0
    while i < n:
        ch = text[i]
        cw = char_width(ch)
        if ch == " ":
            if w + cw > width:
                spans.append((start, i))
                while i < n and text[i] == " ":
                    i += 1
                start, w, brk = i, 0, -1
                continue
            brk = i
            w += cw
            i += 1
            continue
        if w + cw > width and w > 0:
            if brk >= start:
                end = brk
                while end > start and text[end - 1] == " ":
                    end -= 1
                spans.append((start, end))
                ns = brk + 1
                while ns < i and text[ns] == " ":
                    ns += 1
                start = ns
                w = text_width(text[start:i])
                brk = -1
                continue
            spans.append((start, i))
            start, w, brk = i, 0, -1
            continue
        w += cw
        i += 1
    spans.append((start, n))
    return spans


def hard_wrap(text: str, width: int) -> list[str]:
    """Wrap by display width without reflowing (for code/preformatted text)."""
    width = max(1, width)
    out: list[str] = []
    cur: list[str] = []
    w = 0
    for ch in text:
        cw = char_width(ch)
        if w + cw > width and cur:
            out.append("".join(cur))
            cur, w = [], 0
        cur.append(ch)
        w += cw
    out.append("".join(cur))
    return out


def shorten_path(path: str, max_w: int) -> str:
    home = os.path.expanduser("~")
    p = path
    if home and home != os.sep and (p == home or p.startswith(home + os.sep)):
        p = "~" + p[len(home):]
    if text_width(p) <= max_w:
        return p
    parts = [x for x in p.split(os.sep) if x]
    tail: list[str] = []
    for part in reversed(parts):
        cand = "…/" + "/".join([part] + tail)
        if text_width(cand) > max_w:
            break
        tail.insert(0, part)
    if tail:
        return "…/" + "/".join(tail)
    return clip(parts[-1] if parts else p, max_w)


def fmt_elapsed(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s}s" if s < 60 else f"{s // 60}m {s % 60:02d}s"


# --------------------------------------------------------------------------
# Inline markdown-lite
# --------------------------------------------------------------------------

_INLINE_RE = re.compile(r"(`+)(.+?)\1|\*\*(.+?)\*\*")
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*([\w+#.\-]*)\s*$")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_HR_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$")
_TABLE_RE = re.compile(r"^\s*\|")

K_PLAIN, K_CODE, K_BOLD = 0, 1, 2


def parse_inline(text: str) -> tuple[str, list[int]]:
    """Split ``text`` into plain characters plus a style kind per character."""
    plain: list[str] = []
    kinds: list[int] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            seg = text[pos : m.start()]
            plain.append(seg)
            kinds.extend([K_PLAIN] * len(seg))
        if m.group(1):
            seg, kind = m.group(2), K_CODE
        else:
            seg, kind = m.group(3), K_BOLD
        plain.append(seg)
        kinds.extend([kind] * len(seg))
        pos = m.end()
    if pos < len(text):
        seg = text[pos:]
        plain.append(seg)
        kinds.extend([K_PLAIN] * len(seg))
    return "".join(plain), kinds


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------


@dataclass
class Message:
    role: str  # user|assistant|system|error|tool|status
    content: str
    # Optional, used by ``tool`` messages: "" (neutral) | "run" | "ok" | "error"
    status: str = ""


@dataclass
class RenderState:
    messages: list[Message] = field(default_factory=list)
    scroll: int = 0
    follow: bool = True
    status: str = ""
    busy: bool = False
    busy_label: str = ""
    # Animation inputs, set by the event loop (kept out of the renderer so
    # frames stay a pure function of state and are testable).
    tick: int = 0
    elapsed: float = 0.0

    def add(self, role: str, content: str, status: str = "") -> None:
        self.messages.append(Message(role=role, content=str(content), status=status))

    def clear_messages(self) -> None:
        self.messages.clear()
        self.scroll = 0
        self.follow = True


# --------------------------------------------------------------------------
# Renderer
# --------------------------------------------------------------------------

GUTTER = 3        # col 0 pad, col 1 mark, col 2 pad -> text starts at col 3
MAX_BODY = 100    # cap reading width on very wide terminals
TOOL_OUTPUT_LINES = 6


def dock_rows(ibuf: InputBuffer, text_w: int) -> list[tuple[int, int, int]]:
    """Soft-wrap the input buffer into visual rows ``(logical, start, end)``.

    Wrapping is display-only; the buffer and its key semantics are unchanged.
    A line that exactly fills the width gets one extra empty row so the cursor
    at end-of-line has somewhere to sit.
    """
    text_w = max(1, text_w)
    rows: list[tuple[int, int, int]] = []
    for li, line in enumerate(ibuf.lines):
        start, w, last_space = 0, 0, -1
        chunks: list[tuple[int, int]] = []
        i = 0
        while i < len(line):
            ch = line[i]
            cw = char_width(ch)
            if w + cw > text_w and i > start:
                # prefer breaking after the last space on this row
                cut = last_space + 1 if last_space >= start and ch != " " else i
                if cut <= start:
                    cut = i
                chunks.append((start, cut))
                start = cut
                w = text_width(line[start:i])
                last_space = -1
                continue
            if ch == " ":
                last_space = i
            w += cw
            i += 1
        chunks.append((start, len(line)))
        if line and w >= text_w:
            chunks.append((len(line), len(line)))
        rows.extend((li, s, e) for s, e in chunks)
    return rows


def dock_cursor(ibuf: InputBuffer, rows: list[tuple[int, int, int]]) -> tuple[int, int]:
    """Return ``(visual_row_index, display_col)`` of the cursor in ``rows``."""
    cand = [i for i, (li, s, _e) in enumerate(rows) if li == ibuf.row and s <= ibuf.col]
    idx = cand[-1] if cand else 0
    _li, s, _e = rows[idx]
    line = ibuf.lines[ibuf.row] if ibuf.row < len(ibuf.lines) else ""
    return idx, text_width(line[s : ibuf.col])


class TUIRenderer:
    LOGO = list(brand.LOGO)
    LOGO_COMPACT = [brand.NAME]

    def __init__(self, theme) -> None:
        self.theme = theme
        self._cache: dict[tuple, list[str]] = {}

    # ---- small helpers ---------------------------------------------------

    @staticmethod
    def body_width(width: int) -> int:
        return max(8, min(width - GUTTER - 2, MAX_BODY))

    def _gut(self, mark: str = " ", mark_fg: str | None = None, bold: bool = False) -> str:
        t = self.theme
        if mark.strip() == "":
            return " " * GUTTER
        return " " + t.style(mark, fg=mark_fg or t.ACCENT, bold=bold) + " "

    def _runs(self, plain: str, kinds: list[int], start: int, end: int, *, fg: str, bg: str | None = None) -> str:
        t = self.theme
        out: list[str] = []
        i = start
        while i < end:
            k = kinds[i]
            j = i
            while j < end and kinds[j] == k:
                j += 1
            seg = plain[i:j]
            if k == K_CODE:
                out.append(t.style(seg, fg=t.CODE, bg=bg))
            elif k == K_BOLD:
                out.append(t.style(seg, fg=t.TEXT_BRIGHT, bg=bg, bold=True))
            else:
                out.append(t.style(seg, fg=fg, bg=bg))
            i = j
        return "".join(out)

    def _para(self, text: str, width: int, *, fg: str, indent: int = 0, first_prefix: str = "") -> list[str]:
        """Wrap one inline-styled paragraph line (no gutter).

        ``indent`` is both the first-line offset and the hanging indent;
        ``first_prefix`` (visible width == ``indent``) replaces the first
        line's leading spaces, e.g. with a list bullet.
        """
        plain, kinds = parse_inline(text)
        out: list[str] = []
        for n, (s, e) in enumerate(wrap_spans(plain, max(1, width - indent))):
            run = self._runs(plain, kinds, s, e, fg=fg)
            lead = first_prefix if (n == 0 and first_prefix) else " " * indent
            out.append(lead + run)
        return out

    # ---- plain wrapping (compat) ----------------------------------------

    def wrap_text(self, text: str, width: int) -> list[str]:
        width = max(1, width)
        out: list[str] = []
        for raw in text.splitlines() or [""]:
            if raw == "":
                out.append("")
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            body = raw[indent:]
            for s, e in wrap_spans(body, max(1, width - indent)):
                out.append(" " * indent + body[s:e].rstrip(" "))
        return out

    # ---- markdown-lite for assistant text ---------------------------------

    def _code_block(self, lines: list[str], lang: str, body_w: int) -> list[str]:
        t = self.theme
        B = t.CODE_BG
        longest = max((text_width(x) for x in lines), default=0)
        block_w = max(min(body_w, longest + 4), min(body_w, 24), text_width(lang) + 4)
        inner = max(1, block_w - 4)
        g = " " * GUTTER
        blank = t.style(" " * block_w, bg=B)
        out = []
        if lang:
            out.append(g + t.style(pad_ansi("  " + lang, block_w), fg=t.DIM, bg=B))
        else:
            out.append(g + blank)
        for raw in lines:
            for chunk in hard_wrap(raw, inner):
                pad = " " * (inner - text_width(chunk))
                out.append(g + t.style("  " + chunk + pad + "  ", fg=t.TEXT, bg=B))
        out.append(g + blank)
        return out

    def render_markdown(self, text: str, width: int, *, fg: str | None = None) -> list[str]:
        t = self.theme
        fg = fg or t.TEXT
        body_w = self.body_width(width)
        g = " " * GUTTER
        out: list[str] = []
        in_code = False
        lang = ""
        buf: list[str] = []

        def push_blank() -> None:
            if out and out[-1] != "":
                out.append("")

        for raw in text.split("\n"):
            fence = _FENCE_RE.match(raw)
            if in_code:
                if fence and not fence.group(2):
                    out.extend(self._code_block(buf, lang, body_w))
                    in_code, buf, lang = False, [], ""
                else:
                    buf.append(raw)
                continue
            if fence:
                in_code, lang, buf = True, fence.group(2), []
                continue
            if raw.strip() == "":
                push_blank()
                continue
            if _TABLE_RE.match(raw):
                for chunk in hard_wrap(raw.rstrip(), body_w):
                    out.append(g + t.style(chunk, fg=t.MUTED))
                continue
            m = _HEADING_RE.match(raw)
            if m:
                plain, _ = parse_inline(m.group(2))
                for s, e in wrap_spans(plain, body_w):
                    out.append(g + t.style(plain[s:e], fg=t.TEXT_BRIGHT, bold=True))
                continue
            if _HR_RE.match(raw):
                out.append(g + t.style("─" * min(body_w, 40), fg=t.FAINT))
                continue
            m = _QUOTE_RE.match(raw)
            if m:
                for ln in self._para(m.group(1), body_w - 2, fg=t.MUTED):
                    out.append(g + t.style("│ ", fg=t.FAINT) + ln)
                continue
            m = _LIST_RE.match(raw)
            if m:
                ind = min(len(m.group(1)), 12)
                marker = m.group(2)
                if marker[0] in "-*+":
                    mark = t.style("•", fg=t.ACCENT) + " "
                    mw = 2
                else:
                    mark = t.style(marker, fg=t.MUTED) + " "
                    mw = len(marker) + 1
                lines = self._para(m.group(3), body_w, fg=fg, indent=ind + mw, first_prefix=" " * ind + mark)
                out.extend(g + ln for ln in lines)
                continue
            indent = min(len(raw) - len(raw.lstrip(" ")), 12)
            for ln in self._para(raw.strip(), body_w, fg=fg, indent=indent):
                out.append(g + ln)
        if in_code:
            out.extend(self._code_block(buf, lang, body_w))
        while out and out[-1] == "":
            out.pop()
        return out

    # ---- per-role message formatting --------------------------------------

    def _band(self, run: str, width: int, bar_fg: str) -> str:
        t = self.theme
        P = t.PANEL
        head = t.style(" ", bg=P) + t.style("▌", fg=bar_fg, bg=P) + t.style(" ", bg=P)
        pad = max(0, width - GUTTER - visible_len(run))
        return head + run + t.style(" " * pad, bg=P)

    def _format_user(self, text: str, width: int) -> list[str]:
        t = self.theme
        body_w = self.body_width(width)
        if text.strip().startswith("/"):
            # a command echo: quiet, no band, and tight to its output
            out = []
            for n, ln in enumerate(self.wrap_text(text.strip(), body_w)):
                if n == 0:
                    tok_end = ln.find(" ") if " " in ln else len(ln)
                    run = t.style(ln[:tok_end], fg=t.ACCENT_SOFT, bold=True) + t.style(ln[tok_end:], fg=t.MUTED)
                    out.append(self._gut("›", t.ACCENT_SOFT, bold=True) + run)
                else:
                    out.append(" " * GUTTER + t.style(ln, fg=t.MUTED))
            return out
        P = t.PANEL
        out = []
        for ln in self.wrap_text(text, body_w):
            out.append(self._band(t.style(ln, fg=t.TEXT_BRIGHT, bg=P), width, t.ACCENT))
        out.append("")
        return out

    def _format_assistant(self, text: str, width: int) -> list[str]:
        t = self.theme
        out = [self._gut("◦", t.ACCENT) + t.style(t.APP_NAME, fg=t.LAVENDER, bold=True)]
        out.extend(self.render_markdown(text, width))
        out.append("")
        return out

    def _format_error(self, text: str, width: int) -> list[str]:
        t = self.theme
        out = []
        for n, ln in enumerate(self.wrap_text(text, self.body_width(width))):
            gut = self._gut("!", t.ERROR, bold=True) if n == 0 else " " * GUTTER
            out.append(gut + t.style(ln, fg=t.ERROR))
        out.append("")
        return out

    def _format_tool(self, msg: Message, width: int) -> list[str]:
        t = self.theme
        body_w = self.body_width(width)
        lines = msg.content.split("\n")
        head = lines[0].strip()
        name, _, args = head.partition(" ")
        dot = {"ok": t.SUCCESS, "error": t.ERROR, "run": t.ACCENT_SOFT}.get(msg.status, t.ACCENT_DIM)
        title = t.style(clip(name, body_w - 2), fg=t.ACCENT_SOFT, bold=True)
        room = body_w - 2 - text_width(name) - 2
        if args.strip() and room > 3:
            title += "  " + t.style(clip(args.strip(), room), fg=t.MUTED)
        out = [self._gut("●", dot) + title]
        body = [x for x in lines[1:]]
        while body and not body[-1].strip():
            body.pop()
        shown = body[:TOOL_OUTPUT_LINES]
        for ln in shown:
            out.append(" " + t.style("│", fg=t.FAINT) + " " + t.style(clip(ln, body_w), fg=t.DIM))
        if len(body) > len(shown):
            out.append(" " + t.style("│", fg=t.FAINT) + " " + t.style(f"… +{len(body) - len(shown)} more lines", fg=t.FAINT))
        out.append("")
        return out

    # system blocks (command output) get light structure from their shape
    _KV_RE = re.compile(r"^(\s+)([A-Za-z_][\w.\-]*):(\s*)(.*)$")
    _CMD_RE = re.compile(r"^(\s*)(/[\w\-?]+)(\s+)(.*)$")
    _ACTIVE_RE = re.compile(r"^(\s*)\* (.+)$")
    _DASH_RE = re.compile(r"^(\s*)- (.+)$")

    def _style_system_line(self, ln: str) -> str:
        t = self.theme
        m = self._CMD_RE.match(ln)
        if m:
            return m.group(1) + t.style(m.group(2), fg=t.ACCENT_SOFT, bold=True) + m.group(3) + t.style(m.group(4), fg=t.MUTED)
        m = self._KV_RE.match(ln)
        if m:
            if m.group(4):
                return m.group(1) + t.style(m.group(2) + ":", fg=t.DIM) + m.group(3) + t.style(m.group(4), fg=t.TEXT)
            return m.group(1) + t.style(m.group(2) + ":", fg=t.MUTED)
        m = self._ACTIVE_RE.match(ln)
        if m:
            return m.group(1) + t.style("●", fg=t.ACCENT) + " " + t.style(m.group(2), fg=t.TEXT_BRIGHT)
        m = self._DASH_RE.match(ln)
        if m:
            return m.group(1) + t.style("·", fg=t.FAINT) + " " + t.style(m.group(2), fg=t.MUTED)
        if ln.startswith(" "):
            return t.style(ln, fg=t.MUTED)
        return t.style(ln, fg=t.DIM)

    def _format_system(self, msg: Message, width: int) -> list[str]:
        t = self.theme
        body_w = self.body_width(width)
        lines = msg.content.split("\n")
        mark_fg = t.ACCENT_DIM
        out: list[str] = []
        if len(lines) == 1:
            for n, ln in enumerate(self.wrap_text(lines[0], body_w)):
                gut = self._gut("·", mark_fg) if n == 0 else " " * GUTTER
                out.append(gut + t.style(ln, fg=t.MUTED))
        else:
            first = True
            for ln in lines:
                if first and not ln.startswith(" "):
                    out.append(self._gut("·", mark_fg) + t.style(clip(ln, body_w), fg=t.TEXT_BRIGHT, bold=True))
                else:
                    if text_width(ln) <= body_w:
                        out.append(" " * GUTTER + self._style_system_line(ln))
                    else:
                        for wl in self.wrap_text(ln, body_w):
                            out.append(" " * GUTTER + t.style(wl, fg=t.MUTED))
                first = False
        if msg.role != "status":
            out.append("")
        return out

    def format_message(self, msg: Message, width: int) -> list[str]:
        key = (msg.role, msg.content, msg.status, width, self.theme.name, self.theme.APP_NAME)
        hit = self._cache.get(key)
        if hit is not None:
            return list(hit)
        content = sanitize(msg.content)
        m = Message(msg.role, content, msg.status)
        if msg.role == "user":
            lines = self._format_user(content, width)
        elif msg.role == "assistant":
            lines = self._format_assistant(content, width)
        elif msg.role == "error":
            lines = self._format_error(content, width)
        elif msg.role == "tool":
            lines = self._format_tool(m, width)
        elif msg.role in ("system", "status"):
            lines = self._format_system(m, width)
        else:
            lines = [" " * GUTTER + ln for ln in self.wrap_text(content, self.body_width(width))] + [""]
        if len(self._cache) > 1024:
            self._cache.clear()
        self._cache[key] = lines
        return list(lines)

    # ---- welcome / empty state --------------------------------------------

    def render_welcome(
        self,
        width: int,
        version: str,
        engine_name: str = "",
        *,
        cwd: str = "",
        compact: bool = False,
    ) -> list[str]:
        _ = engine_name  # intentionally not shown in the main UI (see /engine, /about)
        t = self.theme
        w = max(20, width)
        g = " " * GUTTER
        lines: list[str] = [""]
        if not compact and w >= GUTTER + brand.LOGO_WIDTH + 2:
            grad = [t.ACCENT_SOFT, t.ACCENT, t.ACCENT_DIM]
            for i, row in enumerate(brand.LOGO):
                lines.append(g + t.style(row.rstrip(), fg=grad[min(i, len(grad) - 1)]))
            lines.append("")
        else:
            lines.append(g + t.style(brand.NAME, fg=t.ACCENT_SOFT, bold=True))
        if compact:
            lines.append(g + t.style("type a message to begin", fg=t.DIM))
            lines.append("")
            return lines
        lines.append(g + t.style(brand.TAGLINE, fg=t.MUTED))
        meta = [f"v{version}"] if version else []
        if cwd:
            meta.append(shorten_path(cwd, max(10, w - 24)))
        meta_s = t.style("  ·  ".join(meta), fg=t.DIM)
        name = t.APP_NAME
        if name.strip().lower() != brand.NAME:
            lines.append(g + t.style(name, fg=t.LAVENDER, bold=True) + (t.style("  ·  ", fg=t.FAINT) + meta_s if meta else ""))
        elif meta:
            lines.append(g + meta_s)
        lines.append("")
        for cmd, desc in (
            ("/help", "commands and shortcuts"),
            ("/name", "rename your assistant"),
            ("/engine", "engine, model and capabilities"),
            ("/about", "environment details"),
        ):
            lines.append(g + t.style(f"{cmd:<9}", fg=t.ACCENT_SOFT, bold=True) + t.style(desc, fg=t.MUTED))
        lines.append("")
        lines.append(g + t.style("type a message to begin", fg=t.DIM))
        lines.append("")
        return lines

    def render_busy(self, state: RenderState, width: int) -> list[str]:
        t = self.theme
        comet = brand.COMET[state.tick % len(brand.COMET)]
        label = state.busy_label or "thinking"
        line = " " + t.style(comet, fg=t.ACCENT_SOFT) + " " + t.style(label, fg=t.MUTED)
        if state.elapsed >= 1:
            line += t.style("  ·  " + fmt_elapsed(state.elapsed), fg=t.DIM)
        return [line, ""]

    # ---- transcript -------------------------------------------------------

    def render_transcript(
        self,
        messages: list[Message],
        width: int,
        *,
        version: str = "",
        engine_name: str = "",
        cwd: str = "",
        show_banner: bool = True,
    ) -> list[str]:
        lines: list[str] = []
        if show_banner or not messages:
            lines.extend(self.render_welcome(width, version, engine_name, cwd=cwd, compact=(not show_banner)))
        for msg in messages:
            lines.extend(self.format_message(msg, width))
        return lines

    def build_transcript(self, state: RenderState, cols: int, *, version: str = "", cwd: str = "", engine_name: str = "", show_banner: bool = True) -> list[str]:
        lines = self.render_transcript(
            state.messages, cols, version=version, engine_name=engine_name, cwd=cwd, show_banner=show_banner
        )
        if state.busy:
            lines.extend(self.render_busy(state, cols))
        return lines

    # ---- layout -----------------------------------------------------------

    @staticmethod
    def dock_text_width(cols: int) -> int:
        return max(1, cols - GUTTER - 1)

    def layout(self, cols: int, rows: int, ibuf: InputBuffer) -> dict:
        header_h = 1
        status_h = 1
        sep_h = 1  # the dock's half-block top edge
        min_viewport = 3
        n_rows = len(dock_rows(ibuf, self.dock_text_width(cols)))
        max_input = max(1, rows - header_h - sep_h - status_h - min_viewport)
        cap = max(3, rows // 3)
        input_h = max(1, min(n_rows, max_input, cap))
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

    def max_scroll(self, state: RenderState, cols: int, rows: int, ibuf: InputBuffer, **ctx) -> int:
        lay = self.layout(cols, rows, ibuf)
        n = len(self.build_transcript(state, cols, **self._ctx(ctx)))
        return max(0, n - lay["viewport"])

    @staticmethod
    def _ctx(ctx: dict) -> dict:
        return {k: ctx[k] for k in ("version", "cwd", "engine_name", "show_banner") if k in ctx}

    # ---- chrome -----------------------------------------------------------

    def paint(self, line: str, cols: int, bg: str | None = None) -> str:
        """Fill exactly ``cols`` cells; keep the surface colour through resets."""
        seq = _bg_seq(bg or self.theme.BG)
        body = truncate_ansi(line, cols) if visible_len(line) > cols else line
        pad = cols - visible_len(body)
        body = body.replace("\033[0m", "\033[0m" + seq)
        return seq + body + (" " * pad if pad > 0 else "") + "\033[0m"

    def render_header(self, cols: int, session_id: str | None, cwd: str) -> str:
        t = self.theme
        left = " " + t.style("◦", fg=t.ACCENT) + " " + t.style(brand.NAME, fg=t.TEXT_BRIGHT, bold=True)
        if t.APP_NAME.strip().lower() != brand.NAME:
            left += t.style("  ·  ", fg=t.FAINT) + t.style(t.APP_NAME, fg=t.LAVENDER, bold=True)
        sess = session_id[:8] if session_id else "new session"
        sess_s = t.style(sess, fg=t.MUTED)
        room = cols - visible_len(left) - text_width(sess) - 6
        right = sess_s + " "
        if room >= 12 and cwd:
            right = t.style(shorten_path(cwd, min(room, max(12, cols // 2))), fg=t.DIM) + t.style("  ·  ", fg=t.FAINT) + right
        gap = cols - visible_len(left) - visible_len(right)
        return left + " " * max(1, gap) + right

    def render_status(self, cols: int, state: RenderState) -> str:
        t = self.theme
        if state.busy:
            comet = brand.COMET[state.tick % len(brand.COMET)]
            left = " " + t.style(comet, fg=t.ACCENT_SOFT) + " " + t.style("working", fg=t.MUTED)
            hints = [("ctrl+c", "interrupt")]
        else:
            label = state.status if state.status and state.status != "ready" else "ready"
            left = " " + t.style("○", fg=t.ACCENT_DIM) + " " + t.style(label, fg=t.DIM)
            hints = [("enter", "send"), ("shift+enter", "newline"), ("/help", "commands")]
        if not state.follow:
            hints = [("scroll down", "to follow")] + hints[:1]
            left += t.style("  ·  ", fg=t.FAINT) + t.style("history", fg=t.WARNING)

        def fmt(hs):
            return "  ".join(t.style(k, fg=t.MUTED) + " " + t.style(v, fg=t.DIM) for k, v in hs) + " "

        room = cols - visible_len(left) - 2
        while hints and visible_len(fmt(hints)) > room:
            hints = hints[:-1]
        right = fmt(hints) if hints else " "
        gap = cols - visible_len(left) - visible_len(right)
        return left + " " * max(1, gap) + right

    def render_dock(self, cols: int, ibuf: InputBuffer, input_h: int, *, busy: bool, placeholder: str) -> tuple[list[str], int, int]:
        """Return ``(rows, cursor_row_in_dock, cursor_col_0based)``."""
        t = self.theme
        P = t.PANEL
        text_w = self.dock_text_width(cols)
        vrows = dock_rows(ibuf, text_w)
        cur_idx, cur_col = dock_cursor(ibuf, vrows)
        total = len(vrows)
        start = 0
        if total > input_h:
            start = min(max(0, cur_idx - input_h + 1), total - input_h)
        first = ibuf.lines[0] if ibuf.lines else ""
        is_cmd = first.startswith("/")
        tok_end = (first.find(" ") if " " in first else len(first)) if is_cmd else 0
        bar_fg = t.ACCENT_DIM if busy else (t.ACCENT_SOFT if is_cmd else t.ACCENT)
        out: list[str] = []
        for i in range(input_h):
            idx = start + i
            head = t.style(" ", bg=P) + t.style("▌", fg=bar_fg, bg=P) + t.style(" ", bg=P)
            if idx >= total:
                out.append(head)
                continue
            li, s, e = vrows[idx]
            line = ibuf.lines[li]
            seg = line[s:e]
            if li == 0 and is_cmd and s < tok_end:
                k = min(e, tok_end) - s
                body = t.style(seg[:k], fg=t.ACCENT_SOFT, bg=P, bold=True) + t.style(seg[k:], fg=t.TEXT_BRIGHT, bg=P)
            else:
                body = t.style(seg, fg=t.TEXT_BRIGHT, bg=P)
            if total == 1 and not line:
                body = t.style(placeholder, fg=t.DIM, bg=P)
            row = head + body
            if i == 0 and start > 0:
                tag = f"↑{start}"
                gap = cols - visible_len(row) - len(tag) - 1
                if gap >= 1:
                    row += t.style(" " * gap, bg=P) + t.style(tag, fg=t.DIM, bg=P)
            out.append(row)
        return out, max(0, min(input_h - 1, cur_idx - start)), cur_col

    # ---- frame ------------------------------------------------------------

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
        show_banner: bool = True,
    ) -> tuple[str, tuple[int, int], bool]:
        t = self.theme
        lay = self.layout(cols, rows, ibuf)
        transcript = self.build_transcript(
            state, cols, version=version, cwd=cwd, engine_name=engine_name, show_banner=show_banner
        )
        vp_h = lay["viewport"]
        max_scroll = max(0, len(transcript) - vp_h)
        if state.follow:
            state.scroll = max_scroll
        else:
            state.scroll = max(0, min(state.scroll, max_scroll))
        visible = transcript[state.scroll : state.scroll + vp_h]
        while len(visible) < vp_h:
            visible.append("")

        out: list[str] = []
        row = 1

        def emit(line: str) -> None:
            nonlocal row
            out.append(f"\033[{row};1H" + line)
            row += 1

        emit(self.paint(self.render_header(cols, session_id, cwd), cols))
        for ln in visible:
            emit(self.paint(ln, cols))
        # dock top edge: lower-half blocks make the panel start mid-row
        emit(t.style("▄" * cols, fg=t.PANEL, bg=t.BG))
        if state.busy:
            ph = f"waiting for {t.APP_NAME}…"
        else:
            ph = f"Message {t.APP_NAME}, or type / for commands"
        dock, cur_row, cur_col = self.render_dock(cols, ibuf, lay["input"], busy=state.busy, placeholder=ph)
        for ln in dock:
            emit(self.paint(ln, cols, bg=t.PANEL))
        emit(self.paint(self.render_status(cols, state), cols, bg=t.PANEL))

        screen_row = lay["header"] + lay["viewport"] + lay["sep"] + 1 + cur_row
        screen_col = max(1, min(cols, 1 + GUTTER + cur_col))
        return "".join(out) + "\033[0m", (screen_row, screen_col), max_scroll > 0
