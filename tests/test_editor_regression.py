"""The input editor is unchanged by the redesign; pin its behaviour."""
from orb1t.input_editor import InputBuffer, KeyParser


def kinds(data: bytes):
    return [(e.kind, e.value) for e in KeyParser().feed(data)]


def test_buffer_editing():
    b = InputBuffer()
    b.insert("hello")
    b.newline()
    b.insert("world")
    assert b.text == "hello\nworld" and (b.row, b.col) == (1, 5)
    b.up()
    assert (b.row, b.col) == (0, 5)
    b.home(); b.delete(); b.kill_to_end()
    assert b.lines[0] == ""
    b.down(); b.backspace()
    assert b.lines == ["world"] and (b.row, b.col) == (0, 0)


def test_insert_filters_control_and_escape():
    b = InputBuffer()
    b.insert("a\x1b[31mb\x07\tc")
    assert "\x1b" not in b.text and "\x07" not in b.text and "    " in b.text


def test_enter_and_shift_enter_forms():
    assert kinds(b"\r") == [("enter", "")]
    for seq in (b"\x1b[13;2u", b"\x1b[27;2;13~", b"\x1b\r"):
        assert kinds(seq) == [("shift_enter", "")], seq


def test_navigation_and_paste_markers():
    assert [k for k, _ in kinds(b"\x1b[A\x1b[B\x1b[C\x1b[D\x1b[H\x1b[F\x1b[3~\x1b[5~\x1b[6~")] == [
        "up", "down", "right", "left", "home", "end", "delete", "page_up", "page_down"]
    assert [k for k, _ in kinds(b"\x1b[200~hi\x1b[201~")] == ["paste_start", "char", "char", "paste_end"]


def test_mouse_wheel_and_utf8():
    assert kinds(b"\x1b[<64;10;5M") == [("scroll_up", "")]
    assert kinds(b"\x1b[<65;10;5M") == [("scroll_down", "")]
    assert kinds("é日".encode()) == [("char", "é"), ("char", "日")]


def test_split_utf8_across_reads():
    p = KeyParser()
    raw = "日".encode()
    assert p.feed(raw[:2]) == []
    assert [e.value for e in p.feed(raw[2:])] == ["日"]
