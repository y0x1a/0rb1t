from orb1t.input_editor import InputBuffer
from orb1t.theme import get_theme
from orb1t.tui import RenderState, TUIRenderer, strip_ansi


def _frame(state, cols=80, rows=24, version="0.2.0", cwd="/tmp", session_id="ses123", engine="opencode"):
    r = TUIRenderer(get_theme("purple", "0rb1t"))
    ib = InputBuffer()
    frame, cursor, _ = r.frame(cols=cols, rows=rows, state=state, ibuf=ib, version=version, cwd=cwd, session_id=session_id, engine_name=engine)
    return frame, strip_ansi(frame), cursor


def test_welcome_screen_visible_when_empty():
    s = RenderState()
    _, plain, _ = _frame(s)
    assert "Get started" in plain
    assert "Type a message to begin." in plain
    assert "opencode" not in plain.lower()


def test_user_and_assistant_messages_visible_in_frame():
    s = RenderState()
    s.add("user", "hello from user")
    s.add("assistant", "assistant reply here")
    _, plain, _ = _frame(s)
    assert "hello from user" in plain
    assert "assistant reply here" in plain


def test_messages_remain_visible_after_many_messages():
    s = RenderState()
    for i in range(30):
        s.add("user", f"user-msg-{i}")
        s.add("assistant", f"assistant-msg-{i}")
    _, plain, _ = _frame(s, rows=24)
    # follow mode should keep latest visible
    assert "assistant-msg-29" in plain
    assert "user-msg-29" in plain


def test_input_dock_stays_at_bottom():
    s = RenderState()
    for i in range(40):
        s.add("assistant", f"line {i}")
    frame, plain, (cr, cc) = _frame(s, rows=20)
    lines = plain.splitlines()
    assert len(lines) == 20
    # status line last, separator and input above it
    assert "/help" in lines[-1] or "enter send" in lines[-1].lower()
    assert "›" in lines[-3] or "›" in "\n".join(lines[-5:-1])


def test_small_terminal_does_not_crash_and_keeps_input():
    s = RenderState()
    s.add("user", "hi")
    s.add("assistant", "hello")
    frame, plain, (cr, cc) = _frame(s, cols=30, rows=10)
    assert cr >= 1 and cc >= 1
    assert len(plain.splitlines()) == 10
