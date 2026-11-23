from conftest import plain, split_rows

from orb1t.input_editor import InputBuffer
from orb1t.theme import get_theme
from orb1t.tui import RenderState, TUIRenderer, strip_ansi


def _frame(state, cols=80, rows=24, version="0.2.0", cwd="/tmp", session_id="ses123", engine="opencode"):
    r = TUIRenderer(get_theme("purple", "0rb1t"))
    ib = InputBuffer()
    frame, cursor, _ = r.frame(cols=cols, rows=rows, state=state, ibuf=ib, version=version, cwd=cwd, session_id=session_id, engine_name=engine)
    return frame, strip_ansi(frame), cursor, split_rows(frame)


def test_welcome_screen_visible_when_empty():
    s = RenderState()
    _, _, _, rows = _frame(s)
    text = "\n".join(plain(r) for r in rows).lower()
    assert ("0rb1t" in text) or ("get started" in text)
    assert "opencode" not in text
    assert "/help" in text or "help" in text


def test_user_and_assistant_messages_visible_in_frame():
    s = RenderState()
    s.add("user", "hello from user")
    s.add("assistant", "assistant reply here")
    _, _, _, rows = _frame(s)
    text = "\n".join(plain(r) for r in rows)
    assert "hello from user" in text
    assert "assistant reply here" in text


def test_messages_remain_visible_after_many_messages():
    s = RenderState()
    for i in range(30):
        s.add("user", f"user-msg-{i}")
        s.add("assistant", f"assistant-msg-{i}")
    _, _, _, rows = _frame(s, rows=24)
    # follow mode should keep latest visible
    text = "\n".join(plain(r) for r in rows)
    assert "assistant-msg-29" in text
    assert "user-msg-29" in text


def test_input_dock_stays_at_bottom():
    s = RenderState()
    for i in range(40):
        s.add("assistant", f"line {i}")
    _, _, (cr, cc), rows = _frame(s, rows=20)
    assert len(rows) >= 10
    text = "\n".join(plain(r) for r in rows)
    assert "/help" in text.lower() or "enter send" in text.lower()
    assert "▌" in text
    # dock band is painted on one of the final rows
    tail = "\n".join(plain(r) for r in rows[-4:])
    assert "▌" in tail or "▄" in tail
    assert 1 <= cr <= 20 and 1 <= cc <= 80


def test_small_terminal_does_not_crash_and_keeps_input():
    s = RenderState()
    s.add("user", "hi")
    s.add("assistant", "hello")
    _, _, (cr, cc), rows = _frame(s, cols=30, rows=10)
    assert cr >= 1 and cc >= 1
    assert len(rows) >= 5
    text = "\n".join(plain(r) for r in rows)
    assert "▌" in text or "Message" in text
