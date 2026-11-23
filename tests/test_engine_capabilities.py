from pathlib import Path

from orb1t.app import App
from orb1t.engines.base import (
    EngineCapabilities,
    EngineHealth,
    EngineRequest,
    EngineResponse,
    SessionInfo,
)
from orb1t.engines.registry import register_engine, unregister_engine
from orb1t.errors import EngineError, UnsupportedCapabilityError


class MockEngine:
    name = "mock"

    def __init__(self, *, healthy=True, installed=True, caps=None, fail_send=False):
        self._healthy = healthy
        self._installed = installed
        self._caps = caps or ["health", "send", "sessions.list"]
        self.fail_send = fail_send
        self.shutdown_called = False
        self.created = []

    def capabilities(self):
        return EngineCapabilities.from_list(self._caps)

    def supports(self, cap):
        return self.capabilities().supports(cap)

    def health(self):
        return EngineHealth(
            ok=self._healthy and self._installed,
            installed=self._installed,
            message="ok" if self._healthy and self._installed else "down",
            detail={"mock": True},
        )

    def info(self):
        h = self.health()
        return {
            "name": self.name,
            "installed": h.installed,
            "healthy": h.ok,
            "status": h.message,
            "capabilities": self.capabilities().declared(),
        }

    def send(self, request: EngineRequest) -> EngineResponse:
        if not self.supports("send"):
            raise UnsupportedCapabilityError(self.name, "send")
        if self.fail_send:
            raise EngineError("boom", code="mock_failure", engine=self.name)
        sid = request.session_id or "sess-mock-1"
        self.created.append(request.message)
        return EngineResponse(text=f"echo:{request.message}", session_id=sid, raw={"ok": True})

    def list_sessions(self, cwd=None):
        if not self.supports("sessions.list"):
            raise UnsupportedCapabilityError(self.name, "sessions.list")
        return [SessionInfo(id="sess-mock-1", title="Mock")]

    def shutdown(self):
        self.shutdown_called = True


def _make_app(tmp_path, monkeypatch, engine_name="mock"):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    app = App(cwd=tmp_path)
    app.config["engine"]["name"] = engine_name
    app.engine = app._build_engine()
    return app


def test_mock_engine_success_and_session(tmp_path, monkeypatch):
    register_engine("mock", lambda cfg: MockEngine())
    try:
        app = _make_app(tmp_path, monkeypatch)
        r1 = app.send("hello")
        assert r1.text == "echo:hello"
        assert r1.session_id == "sess-mock-1"
        r2 = app.send("again", session_id=r1.session_id)
        assert r2.session_id == "sess-mock-1"
    finally:
        unregister_engine("mock")


def test_missing_capability_declared(tmp_path, monkeypatch):
    register_engine("mock", lambda cfg: MockEngine(caps=["health"]))  # no send
    try:
        app = _make_app(tmp_path, monkeypatch)
        info = app.engine.info()
        assert info["capabilities"]["send"] is False
        try:
            app.send("hi")
            assert False, "expected unsupported capability"
        except EngineError as e:
            assert e.code == "unsupported_capability"
            assert e.capability == "send"
    finally:
        unregister_engine("mock")


def test_unavailable_engine_failure(tmp_path, monkeypatch):
    register_engine("mock", lambda cfg: MockEngine(installed=False, healthy=False))
    try:
        app = _make_app(tmp_path, monkeypatch)
        h = app.engine.health()
        assert h.installed is False
        assert h.ok is False
    finally:
        unregister_engine("mock")


def test_engine_failure_normalized(tmp_path, monkeypatch):
    register_engine("mock", lambda cfg: MockEngine(fail_send=True))
    try:
        app = _make_app(tmp_path, monkeypatch)
        try:
            app.send("x")
            assert False, "expected error"
        except EngineError as e:
            assert e.code == "mock_failure"
            assert e.engine == "mock"
    finally:
        unregister_engine("mock")


def test_engine_command_reports_capabilities(tmp_path, monkeypatch):
    register_engine("mock", lambda cfg: MockEngine(caps=["health", "send"]))
    try:
        app = _make_app(tmp_path, monkeypatch)
        res = app.dispatch_command("/engine")
        assert res.ok
        assert "active: mock" in res.message
        assert "capabilities:" in res.message
        assert "send: yes" in res.message
        assert "sessions.list: no" in res.message
    finally:
        unregister_engine("mock")


def test_engine_switch_via_command(tmp_path, monkeypatch):
    eng = MockEngine()
    register_engine("mock", lambda cfg: eng)
    try:
        app = _make_app(tmp_path, monkeypatch, engine_name="opencode")
        # switch to mock
        res = app.dispatch_command("/engine use mock")
        assert res.ok
        assert app.config["engine"]["name"] == "mock"
        assert app.engine.name == "mock"
    finally:
        unregister_engine("mock")
