from orb1t.app import App


def test_app_dispatch_builtin_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    app = App(cwd=tmp_path)
    res = app.dispatch_command("/config get ui.theme")
    assert res.ok
    assert "ui.theme" in res.message


def test_app_theme_set(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    app = App(cwd=tmp_path)
    res = app.dispatch_command("/theme cyan")
    assert res.ok
    assert app.config["ui"]["theme"] == "cyan"


def test_unknown_engine_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    app = App(cwd=tmp_path)
    res = app.dispatch_command("/engine use does-not-exist")
    assert not res.ok
    assert "unknown engine" in res.message.lower()
