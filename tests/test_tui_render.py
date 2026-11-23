import itertools

try:
    import pytest
except Exception:
    import types; pytest=types.SimpleNamespace(skip=lambda *a,**k: (_ for _ in ()).throw(Exception("skip")), mark=types.SimpleNamespace(parametrize=lambda *a,**k: (lambda f:f)))

from conftest import plain, split_rows
from orb1t import brand
from orb1t.input_editor import InputBuffer
from orb1t.theme import get_theme
from orb1t.tui import GUTTER, Message, RenderState, TUIRenderer, text_width, visible_len

CTX = dict(version="9.9.9", cwd="/home/dev/projects/orbit", engine_name="opencode")
MD = ("Intro with `code` and **bold**.\n\n# Heading\n- one\n- two with a very long line that must wrap "
      "around the edge of the viewport properly\n1. first\n> quoted text\n---\n| a | b |\n"
      "```python\nx = 1\nprint('日本語 a very long code line that should hard wrap rather than overflow the card')\n```\ntail")


def make_state(kind: str) -> RenderState:
    s = RenderState()
    if kind == "empty":
        return s
    s.add("user", "hello\nsecond line  with   gaps")
    s.add("user", "/help")
    s.add("system", "Commands\n  /help      Show commands (h, ?)\n  /name      set name\n\nTips: be nice")
    s.add("system", "Engine\n  active: opencode\n  capabilities:\n    - send: yes\n  * purple")
    s.add("assistant", MD)
    s.add("tool", "bash  pytest -q\n" + "\n".join(f"line {i}" for i in range(12)), status="ok")
    s.add("tool", "read", status="run")
    s.add("error", "[engine] boom " * 20)
    s.add("status", "quiet")
    if kind == "busy":
        s.busy, s.busy_label, s.tick, s.elapsed = True, "Nova thinking", 5, 61.0
    if kind == "scrolled":
        s.follow, s.scroll = False, 2
    return s


def make_ibuf(kind: str) -> InputBuffer:
    b = InputBuffer()
    if kind == "text":
        b.set_text("hello world")
    elif kind == "command":
        b.set_text("/theme cyan")
    elif kind == "long":
        b.set_text("word " * 80 + "\n日本語" * 10 + "\nlast")
    elif kind == "cursor_mid":
        b.set_text("word " * 30 + "\nx")
        b.row, b.col = 0, 17
    return b


SIZES = [(20, 8), (24, 10), (34, 12), (40, 14), (60, 20), (80, 24), (100, 30), (140, 40), (200, 50)]
STATES = ["empty", "chat", "busy", "scrolled"]
INPUTS = ["empty", "text", "command", "long", "cursor_mid"]


@pytest.mark.parametrize("name", ["0rb1t", "Nova", "日本語"])
@pytest.mark.parametrize("cols,rows", SIZES)
def test_frame_invariants(cols, rows, name):
    r = TUIRenderer(get_theme("purple", name))
    for st, ib in itertools.product(STATES, INPUTS):
        state, ibuf = make_state(st), make_ibuf(ib)
        frame, (cr, cc), _ = r.frame(cols=cols, rows=rows, state=state, ibuf=ibuf, session_id="abcdef0123456789", **CTX)
        lines = split_rows(frame)
        assert len(lines) == rows, (st, ib)
        for ln in lines:
            assert visible_len(ln) == cols, (cols, rows, st, ib, plain(ln))
        lay = r.layout(cols, rows, ibuf)
        first_dock = lay["header"] + lay["viewport"] + lay["sep"] + 1
        assert first_dock <= cr <= first_dock + lay["input"] - 1
        assert 1 <= cc <= cols
        assert lay["header"] + lay["viewport"] + lay["sep"] + lay["input"] + lay["status"] == rows


def test_frame_never_emits_clear_or_foreign_escapes():
    r = TUIRenderer(get_theme("purple"))
    s = RenderState()
    s.add("assistant", "hi\x1b[2J\x1b]0;pwned\x07\x1b[?1049l done")
    s.add("tool", "x\x1b[2J y\nout\x1b[H", status="ok")
    frame, _, _ = r.frame(cols=80, rows=24, state=s, ibuf=InputBuffer(), session_id=None, **CTX)
    assert "\x1b[2J" not in frame and "pwned" not in frame and "?1049" not in frame
    assert "\x1b[H" not in frame


def test_surface_color_survives_style_resets():
    t = get_theme("purple")
    r = TUIRenderer(t)
    row = r.paint(t.style("a", fg=t.ACCENT) + t.style("b", fg=t.TEXT), 20)
    bg = "\x1b[48;2;11;11;16m"
    # every reset is followed by the surface colour again
    assert row.count("\x1b[0m" + bg) >= 2 and row.startswith(bg)


def test_welcome_logo_and_responsive_fallback():
    t = get_theme("purple", "Nova")
    r = TUIRenderer(t)
    wide = [plain(x) for x in r.render_welcome(100, "1.2.3", "opencode", cwd="/x/y")]
    for row in brand.LOGO:
        assert any(row.rstrip() in ln for ln in wide)
    txt = "\n".join(wide)
    assert "Nova" in txt and "v1.2.3" in txt and "/engine" in txt and "/help" in txt
    assert "opencode" not in txt.lower()            # engine stays out of the main UI
    narrow = "\n".join(plain(x) for x in r.render_welcome(24, "1.2.3"))
    assert brand.LOGO[0].rstrip() not in narrow and "0rb1t" in narrow
    for w in (20, 24, 40):
        assert all(visible_len(x) <= max(w, 80) for x in r.render_welcome(w, "1"))


def test_default_name_is_not_duplicated():
    r = TUIRenderer(get_theme("purple", "0rb1t"))
    hdr = plain(r.render_header(80, None, "/x"))
    assert hdr.count("0rb1t") == 1
    r2 = TUIRenderer(get_theme("purple", "Nova"))
    hdr2 = plain(r2.render_header(80, "abcdef0123", "/x"))
    assert "0rb1t" in hdr2 and "Nova" in hdr2 and "abcdef01" in hdr2 and "abcdef012" not in hdr2


def test_header_degrades_gracefully():
    r = TUIRenderer(get_theme("purple", "Nova"))
    for cols in (20, 30, 50, 120):
        assert visible_len(r.paint(r.render_header(cols, "abcdef0123", "/a/b/c"), cols)) == cols


def test_user_and_assistant_share_text_column():
    r = TUIRenderer(get_theme("purple", "Nova"))
    u = [plain(x) for x in r.format_message(Message("user", "hello"), 80)]
    a = [plain(x) for x in r.format_message(Message("assistant", "world"), 80)]
    assert u[0][GUTTER:].startswith("hello") and u[0][1] == "▌"
    assert a[0][GUTTER:].startswith("Nova") and a[1][GUTTER:].startswith("world")
    assert visible_len(r.format_message(Message("user", "hello"), 80)[0]) == 80   # full-bleed band


def test_command_echo_is_quiet_and_tight():
    r = TUIRenderer(get_theme("purple"))
    lines = r.format_message(Message("user", "/theme cyan"), 80)
    assert len(lines) == 1 and "▌" not in plain(lines[0]) and "/theme cyan" in plain(lines[0])


def test_markdown_rendering():
    r = TUIRenderer(get_theme("purple"))
    out = [plain(x) for x in r.format_message(Message("assistant", MD), 60)]
    txt = "\n".join(out)
    assert "```" not in txt and "**" not in txt and "`code`" not in txt
    assert "•" in txt and "python" in txt and "# Heading" not in txt and "Heading" in txt
    # code block: every card row has the same width; nothing overflows
    for ln in out:
        assert text_width(ln) <= 60 - 1


def test_code_block_unclosed_fence_is_rendered():
    r = TUIRenderer(get_theme("purple"))
    out = "\n".join(plain(x) for x in r.format_message(Message("assistant", "```sh\nls -la"), 60))
    assert "ls -la" in out and "```" not in out


def test_tool_block_status_and_truncation():
    t = get_theme("purple")
    r = TUIRenderer(t)
    body = "bash  pytest -q\n" + "\n".join(f"l{i}" for i in range(10))
    ok = r.format_message(Message("tool", body, "ok"), 80)
    err = r.format_message(Message("tool", body, "error"), 80)
    assert "\x1b[38;2;134;239;172m" in ok[0]
    assert "\x1b[38;2;251;113;133m" in err[0]
    txt = "\n".join(plain(x) for x in ok)
    assert "bash" in txt and "pytest -q" in txt and "+4 more lines" in txt and "l9" not in txt


def test_system_block_structure():
    r = TUIRenderer(get_theme("purple"))
    msg = Message("system", "Commands\n  /help      Show commands\n  active: yes\nTips: x")
    out = r.format_message(msg, 80)
    txt = [plain(x) for x in out]
    assert txt[0].strip().startswith("· Commands") or "Commands" in txt[0]
    assert "\x1b[38;2;144;97;249m" in out[1]          # command in soft accent
    assert out[-1] == ""                               # blocks are separated


def test_busy_line_animates_and_shows_elapsed():
    r = TUIRenderer(get_theme("purple", "Nova"))
    s = RenderState(busy=True, busy_label="Nova thinking", elapsed=75, tick=0)
    a = r.render_busy(s, 80)
    s.tick = 1
    b = r.render_busy(s, 80)
    assert a != b
    assert "Nova thinking" in plain(a[0]) and "1m 15s" in plain(a[0])
    s.elapsed = 0.2
    assert "·" not in plain(r.render_busy(s, 80)[0])


def test_busy_line_is_part_of_scroll_extent():
    r = TUIRenderer(get_theme("purple"))
    s = make_state("chat")
    ib = InputBuffer()
    base = r.max_scroll(s, 80, 24, ib, **CTX)
    s.busy = True
    assert r.max_scroll(s, 80, 24, ib, **CTX) > base


def test_follow_pins_to_bottom_and_manual_scroll_is_clamped():
    r = TUIRenderer(get_theme("purple"))
    s = make_state("chat")
    r.frame(cols=80, rows=24, state=s, ibuf=InputBuffer(), session_id=None, **CTX)
    mx = r.max_scroll(s, 80, 24, InputBuffer(), **CTX)
    assert s.scroll == mx > 0
    s.follow, s.scroll = False, 10_000
    _f, _c, scrollable = r.frame(cols=80, rows=24, state=s, ibuf=InputBuffer(), session_id=None, **CTX)
    assert s.scroll == mx and scrollable


def test_status_bar_states():
    r = TUIRenderer(get_theme("purple"))
    idle = plain(r.render_status(100, RenderState()))
    assert "ready" in idle and "enter" in idle and "/help" in idle
    busy = plain(r.render_status(100, RenderState(busy=True)))
    assert "working" in busy and "ctrl+c" in busy
    hist = plain(r.render_status(100, RenderState(follow=False)))
    assert "history" in hist and "scroll down" in hist
    assert "interrupted" in plain(r.render_status(100, RenderState(status="interrupted")))
    for cols in (20, 30, 40, 60):
        assert visible_len(r.paint(r.render_status(cols, RenderState()), cols)) == cols


def test_dock_placeholder_command_mode_and_cursor():
    t = get_theme("purple", "Nova")
    r = TUIRenderer(t)
    rows, cr, cc = r.render_dock(80, InputBuffer(), 1, busy=False, placeholder="Message Nova")
    assert "Message Nova" in plain(rows[0]) and "▌" in plain(rows[0])
    b = InputBuffer()
    b.set_text("/theme cyan")
    rows, cr, cc = r.render_dock(80, b, 1, busy=False, placeholder="x")
    assert "x" not in plain(rows[0]).replace("/theme cyan", "")
    assert cc == len("/theme cyan") and "\x1b[38;2;144;97;249m" in rows[0]
    busy_rows, *_ = r.render_dock(80, b, 1, busy=True, placeholder="x")
    assert "\x1b[38;2;76;29;149m" in busy_rows[0]       # dim bar while the engine works


def test_dock_height_grows_then_caps():
    r = TUIRenderer(get_theme("purple"))
    b = InputBuffer()
    heights = []
    for n in range(1, 30):
        b.set_text("\n".join(["x"] * n))
        heights.append(r.layout(80, 24, b)["input"])
    assert heights[0] == 1 and heights == sorted(heights)
    assert max(heights) == 8 and r.layout(80, 24, b)["viewport"] >= 3


def test_dock_shows_overflow_marker_when_scrolled():
    r = TUIRenderer(get_theme("purple"))
    b = InputBuffer()
    b.set_text("\n".join(f"line{i}" for i in range(20)))
    lay = r.layout(80, 24, b)
    rows, cur, _ = r.render_dock(80, b, lay["input"], busy=False, placeholder="")
    assert "↑" in plain(rows[0]) and "line19" in plain(rows[cur])


def test_theme_variants_change_accent_only():
    for name in ("cyan", "green", "red", "amber", "pink", "mono"):
        t = get_theme(name)
        assert t.name == name and t.BG == get_theme("purple").BG and t.ACCENT != get_theme("purple").ACCENT
        r = TUIRenderer(t)
        frame, *_ = r.frame(cols=80, rows=24, state=make_state("chat"), ibuf=InputBuffer(), session_id=None, **CTX)
        assert len(split_rows(frame)) == 24


def test_format_cache_is_keyed_on_width_and_name():
    r = TUIRenderer(get_theme("purple", "A"))
    m = Message("assistant", "x " * 100)
    assert len(r.format_message(m, 40)) != len(r.format_message(m, 120))
    assert r.format_message(m, 40) == r.format_message(m, 40)
    r2 = TUIRenderer(get_theme("purple", "B"))
    assert plain(r.format_message(m, 40)[0]) != plain(r2.format_message(m, 40)[0])


def test_show_banner_false_uses_compact_empty_state():
    r = TUIRenderer(get_theme("purple"))
    s = RenderState()
    full = r.build_transcript(s, 100, version="1", show_banner=True)
    small = r.build_transcript(s, 100, version="1", show_banner=False)
    assert len(small) < len(full)
    s.add("system", "hi")
    assert len(r.build_transcript(s, 100, version="1", show_banner=False)) < len(r.build_transcript(s, 100, version="1", show_banner=True))


def test_legacy_contract_still_available():
    r = TUIRenderer(get_theme("purple"))
    assert r.wrap_text("a b c", 3) == ["a b", "c"]
    assert r.render_transcript([], 80, version="1", engine_name="x")
    assert isinstance(r.layout(80, 24, InputBuffer()), dict) and set(r.layout(80, 24, InputBuffer())) == {"header", "viewport", "sep", "input", "status"}
    m = Message("user", "x")            # two-arg construction still works
    assert m.status == ""
