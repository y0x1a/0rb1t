from orb1t.tui import (
    char_width, clip, dock_cursor, dock_rows, fmt_elapsed, hard_wrap, pad_ansi, parse_inline,
    sanitize, shorten_path, strip_ansi, text_width, truncate_ansi, visible_len, wrap_spans,
    K_BOLD, K_CODE, K_PLAIN,
)
from orb1t.input_editor import InputBuffer


def test_widths():
    assert text_width("abc") == 3
    assert text_width("日本") == 4
    assert text_width("e\u0301") == 1            # combining mark
    assert char_width("\u200b") == 0
    assert visible_len("\x1b[38;2;1;2;3mhi\x1b[0m") == 2


def test_truncate_and_pad_are_width_aware():
    s = "\x1b[1m日本語\x1b[0m"
    t = truncate_ansi(s, 5)
    assert visible_len(t) <= 5 and visible_len(t) == 4   # a wide char never straddles the edge
    assert t.endswith("\x1b[0m")
    assert visible_len(pad_ansi("日", 6)) == 6
    assert truncate_ansi("abc", 0) == ""


def test_clip_adds_ellipsis():
    assert clip("hello world", 8) == "hello w…"
    assert clip("hi", 8) == "hi"
    assert text_width(clip("日本語日本語", 7)) <= 7


def test_sanitize_strips_terminal_control():
    nasty = "ok\x1b[2Jgone\x1b]0;title\x07 \x1b[31mred\x1b[0m\rline2\x00\x07 tab\there"
    out = sanitize(nasty)
    assert "\x1b" not in out and "\x07" not in out and "\x00" not in out
    assert "title" not in out
    assert "\n" in out                     # CR became a line break
    assert "\t" not in out                 # tabs expanded


def test_wrap_spans_cover_text_and_respect_width():
    text = "the quick brown fox jumps over the lazy dog " * 3
    for w in (5, 11, 20, 40):
        spans = wrap_spans(text, w)
        for s, e in spans:
            assert text_width(text[s:e].rstrip()) <= w
        joined = " ".join(text[s:e].strip() for s, e in spans if text[s:e].strip())
        assert joined.split() == text.split()


def test_wrap_hard_breaks_long_words_and_wide_chars():
    spans = wrap_spans("x" * 25, 10)
    assert [e - s for s, e in spans] == [10, 10, 5]
    assert all(text_width("日本語日本語"[s:e]) <= 3 for s, e in wrap_spans("日本語日本語", 3))
    assert wrap_spans("", 10) == [(0, 0)]


def test_hard_wrap():
    assert hard_wrap("abcdef", 4) == ["abcd", "ef"]
    assert hard_wrap("", 4) == [""]


def test_parse_inline():
    plain, kinds = parse_inline("a `b` **c** d")
    assert plain == "a b c d"
    assert kinds == [K_PLAIN, K_PLAIN, K_CODE, K_PLAIN, K_BOLD, K_PLAIN, K_PLAIN]
    # unbalanced markers stay literal
    assert parse_inline("5 ** 3")[0] == "5 ** 3"


def test_shorten_path_and_elapsed():
    assert text_width(shorten_path("/a/very/long/path/to/some/project", 14)) <= 14
    assert shorten_path("/x", 10) == "/x"
    assert fmt_elapsed(4.9) == "4s" and fmt_elapsed(75) == "1m 15s"


def test_dock_rows_cover_buffer_and_cursor_is_valid():
    b = InputBuffer()
    b.set_text("alpha beta gamma delta epsilon\n\nzeta")
    for w in (4, 9, 16):
        rows = dock_rows(b, w)
        for li in range(len(b.lines)):
            mine = [(s, e) for l, s, e in rows if l == li]
            assert mine[0][0] == 0 and mine[-1][1] == len(b.lines[li])
            assert all(a[1] == c[0] for a, c in zip(mine, mine[1:]))
        for r in range(len(b.lines)):
            for c in range(len(b.lines[r]) + 1):
                b.row, b.col = r, c
                idx, col = dock_cursor(b, rows)
                assert 0 <= idx < len(rows) and 0 <= col <= w


def test_full_width_line_gets_cursor_row():
    b = InputBuffer()
    b.set_text("abcd")
    rows = dock_rows(b, 4)
    assert rows[-1] == (0, 4, 4)
    assert dock_cursor(b, rows) == (len(rows) - 1, 0)
