import queue
import threading

try:
    import pytest
except Exception:
    import types; pytest=types.SimpleNamespace(skip=lambda *a,**k: (_ for _ in ()).throw(Exception("skip")), mark=types.SimpleNamespace(parametrize=lambda *a,**k: (lambda f:f)))

from _fakeapp import FakeApp, FakeTerm
from conftest import plain, split_rows
from orb1t import cli
from orb1t.input_editor import KeyEvent


@pytest.fixture
def tui():
    t = cli.ReplTUI(FakeApp())
    t.term = FakeTerm(80, 24)
    t.set_status("ready")
    return t


def key(t, kind, value=""):
    t._handle_key(KeyEvent(kind, value))


def type_text(t, s):
    for ch in s:
        key(t, "char", ch)


def pump(t, timeout=3.0):
    """Process queued worker results like the main loop does."""
    kind, payload = t.events.get(timeout=timeout)
    assert kind == "worker"
    t._handle_worker(payload)


def test_typing_editing_and_multiline(tui):
    type_text(tui, "helo")
    key(tui, "left"); type_text(tui, "l"); key(tui, "end")
    key(tui, "shift_enter"); type_text(tui, "x")
    assert tui.ibuf.text == "hello\nx"
    key(tui, "backspace"); key(tui, "backspace")
    assert tui.ibuf.text == "hello"
    key(tui, "ctrl_u")
    assert tui.ibuf.text == ""


def test_command_dispatch_goes_through_app(tui):
    type_text(tui, "/version"); key(tui, "enter")
    assert tui.app.commands == ["/version"]
    assert [(m.role, m.content) for m in tui.state.messages] == [("user", "/version"), ("system", "0rb1t vTEST")]
    assert tui.ibuf.text == "" and not tui._busy


def test_failed_command_is_an_error_message(tui):
    type_text(tui, "/nope"); key(tui, "enter")
    assert tui.state.messages[-1].role == "error"


def test_exit_clear_new_session(tui):
    tui.session_id = "abc"
    type_text(tui, "/new"); key(tui, "enter")
    assert tui.session_id is None
    tui.state.add("system", "x")
    type_text(tui, "/clear"); key(tui, "enter")
    assert tui.state.messages == []
    type_text(tui, "/exit"); key(tui, "enter")
    assert tui._stop is True


def test_message_roundtrip_keeps_session(tui):
    type_text(tui, "hi there"); key(tui, "enter")
    assert tui._busy and tui.state.busy and tui._busy_started is not None
    pump(tui)
    assert not tui._busy and tui._busy_started is None
    assert tui.session_id == "sess-0123456789"
    assert [m.role for m in tui.state.messages] == ["user", "assistant"]
    assert tui.state.messages[-1].content == "echo: hi there"
    type_text(tui, "again"); key(tui, "enter")
    pump(tui)
    assert tui.app.sent == [("hi there", None), ("again", "sess-0123456789")]


def test_engine_error_becomes_error_message(tui):
    type_text(tui, "boom"); key(tui, "enter"); pump(tui)
    assert tui.state.messages[-1].role == "error" and "exploded" in tui.state.messages[-1].content
    assert not tui._busy


def test_input_locked_while_busy_but_scroll_allowed():
    gate = threading.Event()
    t = cli.ReplTUI(FakeApp(gate=gate))
    t.term = FakeTerm(80, 24)
    for i in range(40):
        t.state.add("system", f"line {i}")
    type_text(t, "go"); key(t, "enter")
    assert t._busy
    type_text(t, "ignored")
    assert t.ibuf.text == ""
    key(t, "scroll_up")
    assert t.state.follow is False
    gate.set(); pump(t)


def test_ctrl_c_interrupts_and_ignores_stale_result():
    gate = threading.Event()
    t = cli.ReplTUI(FakeApp(gate=gate))
    t.term = FakeTerm(80, 24)
    type_text(t, "slow"); key(t, "enter")
    key(t, "ctrl_c")
    assert not t._busy and t._busy_started is None and t.state.status == "interrupted"
    gate.set()
    kind, payload = t.events.get(timeout=3)
    t._handle_worker(payload)                       # stale worker id -> dropped
    assert [m.role for m in t.state.messages] == ["user", "system"]


def test_ctrl_c_idle_and_ctrl_d(tui):
    key(tui, "ctrl_c")
    assert "/exit" in tui.state.messages[-1].content
    type_text(tui, "x"); key(tui, "ctrl_d")
    assert not tui._stop
    key(tui, "ctrl_u"); key(tui, "ctrl_d")
    assert tui._stop


def test_paste_mode_inserts_as_one_block(tui):
    key(tui, "paste_start")
    type_text(tui, "a"); key(tui, "enter"); type_text(tui, "b")
    key(tui, "paste_end")
    assert tui.ibuf.text == "a\nb" and not tui.app.sent


def test_scroll_follow_semantics(tui):
    for i in range(60):
        tui.state.add("system", f"line {i}")
    tui.render()
    assert tui.state.follow
    key(tui, "scroll_up")
    assert tui.state.follow is False
    pos = tui.state.scroll
    tui.render()
    assert tui.state.scroll == pos                    # new frames don't yank the view
    key(tui, "page_up")
    assert tui.state.scroll < pos
    for _ in range(100):
        key(tui, "scroll_down")
    assert tui.state.follow is True                   # resumes at the bottom
    key(tui, "up"); key(tui, "up")                    # empty input: Up scrolls history
    assert tui.state.follow is False


def test_submit_snaps_back_to_follow(tui):
    for i in range(60):
        tui.state.add("system", f"l{i}")
    key(tui, "scroll_up")
    type_text(tui, "/version"); key(tui, "enter")
    assert tui.state.follow is True


def test_render_is_diffed_and_ctrl_l_forces_repaint(tui):
    tui.render()
    first = tui.term.take()
    assert first and "\x1b[?25l" in first and "\x1b[?2026h" in first and first.endswith("\x1b[?2026l")
    tui.render()
    assert tui.term.take() == ""                      # idle: nothing written
    key(tui, "ctrl_l")
    tui.render()
    assert tui.term.take() != ""
    type_text(tui, "x")
    tui.render()
    assert tui.term.take() != ""


def test_render_never_clears_whole_screen_except_on_resize(tui):
    tui.render()
    assert "\x1b[2J" not in tui.term.take()
    type_text(tui, "abc"); tui.render()
    assert "\x1b[2J" not in tui.term.take()
    tui.term.cols, tui.term.rows = 60, 20
    tui.render()
    out = tui.term.take()
    assert "\x1b[2J" in out
    rows = split_rows(out)
    assert len(rows) == 20


def test_busy_animates_between_renders(tui, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(cli.time, "monotonic", lambda: clock[0])
    tui._busy, tui.state.busy = True, True
    tui._busy_started = 100.0
    tui.render(); tui.term.take()
    clock[0] += 0.5
    tui.render()
    assert tui.term.take() != ""                      # spinner advanced -> repaint
    assert tui.state.elapsed == pytest.approx(0.5)


def test_theme_and_name_changes_apply_live(tui):
    tui.render()
    a = tui.renderer()
    assert tui.renderer() is a                        # renderer (and its cache) is reused
    tui.app.config["ui"]["name"] = "Nova"
    tui.render()
    assert tui.renderer() is not a
    assert any("Nova" in plain(r) for r in split_rows(tui.term.take()))
    tui.app.config["ui"]["theme"] = "cyan"
    assert tui.renderer().theme.name == "cyan"


def test_show_banner_config_is_honoured(tui):
    tui.render(); full = tui.term.take()
    tui.app.config["ui"]["show_banner"] = False
    tui.render(); small = tui.term.take()
    assert "terminal intelligence environment" in "".join(plain(r) for r in split_rows(full))
    assert "terminal intelligence environment" not in "".join(plain(r) for r in split_rows(small))


def test_engine_name_never_in_main_ui(tui):
    tui.app.config["engine"]["name"] = "opencode"
    tui.render()
    assert "opencode" not in "".join(plain(r) for r in split_rows(tui.term.take())).lower()


def test_read_event_prefers_queue_and_handles_idle(tui, monkeypatch):
    tui.events.put(("resize", None))
    assert tui._read_event(0.01) == ("resize", None)
    monkeypatch.setattr(cli.select, "select", lambda *a, **k: ([], [], []))
    assert tui._read_event(0.01) is None
    tui.events.put(("worker", {}))                    # arrives while waiting
    monkeypatch.setattr(cli.select, "select", lambda *a, **k: ([], [], []))
    assert tui._read_event(0.01) == ("worker", {})


def test_discord_presence_refreshes_every_minute(tui, monkeypatch):
    calls = []
    tui.app.update_discord_presence = lambda: calls.append(1) or {"enabled": True}
    tui.app.config["integrations"] = {"discord": {"enabled": True}}
    clock = [100.0]
    monkeypatch.setattr(cli.time, "monotonic", lambda: clock[0])
    tui._discord_next_refresh = 160.0

    tui._refresh_discord_if_due()
    assert calls == []                                 # not due yet

    clock[0] = 160.0
    tui._refresh_discord_if_due()
    tui._refresh_discord_if_due()
    assert len(calls) == 1                             # one refresh per interval

    clock[0] = 220.0
    tui._refresh_discord_if_due()
    assert len(calls) == 2

    tui.app.config["integrations"]["discord"]["enabled"] = False
    clock[0] = 280.0
    tui._refresh_discord_if_due()
    assert len(calls) == 2                             # disabled: no calls


def test_discord_refresh_failure_never_breaks_loop(tui, monkeypatch):
    def boom():
        raise RuntimeError("ipc gone")
    tui.app.update_discord_presence = boom
    tui.app.config["integrations"] = {"discord": {"enabled": True}}
    monkeypatch.setattr(cli.time, "monotonic", lambda: 500.0)
    tui._discord_next_refresh = 0.0
    tui._refresh_discord_if_due()                       # must not raise


def test_cleanup_restores_terminal_and_integrations(tui):
    tui._cleanup()
    assert tui.term.cleaned == 1 and tui.app.shutdowns == 1
    assert "\x1b[?2004l" in tui.term.take() and tui._stop


def test_plain_mode_still_works(monkeypatch, capsys):
    app = FakeApp()
    t = cli.ReplTUI(app)
    lines = iter(["/version", "hello", ""])
    def fake_input(prompt=""):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli, "_is_tty", lambda: False)
    assert t._run_plain() == 0
    out = capsys.readouterr().out
    assert "0rb1t vTEST" in out and "echo: hello" in out and "\x1b" not in out


def test_one_shot_is_plain_text(monkeypatch, capsys):
    monkeypatch.setattr(cli, "App", FakeApp)
    assert cli.main(["--once", "ping"]) == 0
    assert capsys.readouterr().out.strip() == "echo: ping"
    assert cli.main(["boom now"]) == 1
    assert "error:" in capsys.readouterr().err


def test_plain_mode_on_a_tty_is_branded_but_functional(monkeypatch, capsys):
    t = cli.ReplTUI(FakeApp())
    prompts = []
    lines = iter(["hello"])
    def fake_input(prompt=""):
        prompts.append(prompt)
        try:
            return next(lines)
        except StopIteration:
            raise EOFError
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    assert t._run_plain() == 0
    out = plain(capsys.readouterr().out)
    assert cli.brand.LOGO[1].rstrip() in out and "echo: hello" in out
    assert prompts[0] == "› " and "\x1b" not in prompts[0]      # prompt stays escape-free (readline-safe)
