import time, tempfile, os
from pathlib import Path
from orb1t.app import App
from orb1t.cli import ReplTUI
from orb1t.engines.base import EngineResponse
from orb1t.tui import TUIRenderer, strip_ansi


def test_tui_submit_and_response_visible(monkeypatch):
    tmp=Path(tempfile.mkdtemp()); monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp/'cfg'))
    app=App(cwd=tmp)
    app.engine.send=lambda req: EngineResponse(text='assistant says hi', session_id='ses1')
    app.update_discord_presence=lambda: {'enabled':False,'client_id_configured':False,'client_detected':False,'connected':False,'last_update_ok':None,'last_error':'disabled','last_socket':''}
    app.shutdown_integrations=lambda: None
    tui=ReplTUI(app)
    tui.ibuf.insert('hello there')
    tui._submit()
    time.sleep(0.25)
    tui._drain_worker_events(render=False)
    r=TUIRenderer(tui.theme())
    frame,_,_=r.frame(cols=100,rows=28,state=tui.state,ibuf=tui.ibuf,version='0.2.0',cwd=str(app.cwd),session_id=tui.session_id,engine_name='opencode')
    plain=strip_ansi(frame)
    assert 'hello there' in plain
    assert 'assistant says hi' in plain
    assert tui.session_id == 'ses1'


def test_discord_status_command_reports_missing_config(monkeypatch):
    tmp=Path(tempfile.mkdtemp()); monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp/'cfg'))
    app=App(cwd=tmp)
    res=app.dispatch_command('/discord status')
    assert res.ok
    assert 'enabled: False' in res.message
    assert 'client_id: missing' in res.message
    assert 'ABCD' not in res.message
