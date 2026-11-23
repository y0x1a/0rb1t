from orb1t.input_editor import InputBuffer
from orb1t.theme import get_theme
from orb1t.tui import RenderState, TUIRenderer


def test_render_frame_small_terminal():
    r = TUIRenderer(get_theme('purple', '0rb1t'))
    s = RenderState()
    s.add('system', 'hello')
    b = InputBuffer(); b.insert('hi')
    frame, (cr, cc), _ = r.frame(cols=40, rows=12, state=s, ibuf=b, version='0.2.0', cwd='/tmp', session_id=None, engine_name='opencode')
    assert isinstance(frame, str)
    assert cr >= 1 and cc >= 1


def test_follow_mode_stops_on_scroll_up():
    r = TUIRenderer(get_theme('purple'))
    s = RenderState()
    for i in range(50):
        s.add('assistant', f'line {i}\n'+'text '*20)
    b = InputBuffer()
    # initial render follows bottom
    r.frame(cols=60, rows=16, state=s, ibuf=b, version='0', cwd='.', session_id=None, engine_name='opencode')
    assert s.follow is True
    bottom = s.scroll
    s.follow = False
    s.scroll = max(0, bottom - 5)
    r.frame(cols=60, rows=16, state=s, ibuf=b, version='0', cwd='.', session_id=None, engine_name='opencode')
    assert s.follow is False
    assert s.scroll <= bottom


def test_input_dock_keeps_cursor_visible():
    r = TUIRenderer(get_theme('purple'))
    s = RenderState()
    b = InputBuffer()
    for i in range(10):
        b.insert(f'line{i}')
        b.newline()
    b.insert('end')
    frame, (cr, cc), _ = r.frame(cols=50, rows=14, state=s, ibuf=b, version='0', cwd='.', session_id=None, engine_name='opencode')
    assert cr <= 14
    assert cc <= 50
