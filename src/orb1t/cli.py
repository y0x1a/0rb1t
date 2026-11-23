"""CLI entrypoint for 0rb1t."""

from __future__ import annotations

import argparse
import atexit
import os
import queue
import select
import signal
import sys
import threading
import time

from . import __version__
from .app import App
from .errors import EngineError
from .input_editor import InputBuffer, KeyParser
from .terminal import Terminal
from .theme import get_theme
from .tui import RenderState, TUIRenderer


def _is_tty() -> bool:
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def run_once(app: App, message: str, session_id: str | None = None) -> int:
    try:
        resp = app.send(message, session_id=session_id)
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    text = (resp.text or "").strip() or "(no response)"
    print(text)
    return 0


class ReplTUI:
    def __init__(self, app: App) -> None:
        self.app = app
        self.term = Terminal()
        self.ibuf = InputBuffer()
        self.parser = KeyParser()
        self.state = RenderState()
        self.events: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._stop = False
        self._busy = False
        self._worker: threading.Thread | None = None
        self._active_worker_id = 0
        self.session_id: str | None = None
        self._paste_mode = False
        self._paste_buf: list[str] = []

    def theme(self):
        ui = self.app.config.get("ui", {})
        name = str(ui.get("theme", "purple"))
        app_name = str(ui.get("name", "0rb1t"))
        return get_theme(name, app_name=app_name)

    def render(self) -> None:
        cols, rows = self.term.size()
        th = self.theme()
        renderer = TUIRenderer(th)
        engine_name = str(self.app.config.get("engine", {}).get("name", "engine"))
        frame, (cr, cc), _ = renderer.frame(
            cols=cols,
            rows=rows,
            state=self.state,
            ibuf=self.ibuf,
            version=__version__,
            cwd=str(self.app.cwd),
            session_id=self.session_id,
            engine_name=engine_name,
        )
        # Full redraw; simple and robust. Hide cursor during paint.
        buf = "\033[?25l" + frame + f"\033[{cr};{cc}H\033[?25h"
        self.term.write(buf)
        self.term.flush()

    def set_status(self, text: str = "", busy: bool = False, busy_label: str = "") -> None:
        self.state.status = text
        self.state.busy = busy
        self.state.busy_label = busy_label

    def start(self) -> int:
        if not self.term.is_tty:
            return self._run_plain()
        # initial state
        self.set_status("ready", busy=False)
        self._install_signals()
        atexit.register(self.term.cleanup)
        atexit.register(self.app.shutdown_integrations)
        try:
            self.term.enter_alt()
            self.term.enable_raw()
            self.term.enable_mouse()
            self.term.write("\033[?2004h")  # bracketed paste
            self.term.flush()
            self._boot_messages()
            self.render()
            return self.loop()
        finally:
            self._cleanup()

    def _boot_messages(self) -> None:
        # Welcome screen is rendered by TUI when transcript is empty.
        # Add only non-blocking diagnostics.
        try:
            self.app.engine.ensure_available()
        except EngineError as e:
            self.state.add("error", str(e))
        # Optional Discord diagnostics (non-blocking)
        st = self.app.update_discord_presence()
        if st.get("enabled") and not st.get("client_id_configured"):
            self.state.add("system", "Discord Rich Presence enabled but client_id missing. Use /discord status.")
        elif st.get("enabled") and st.get("client_id_configured") and not st.get("last_update_ok"):
            err = st.get("last_error") or "Discord not detected"
            self.state.add("system", f"Discord Rich Presence not active: {err}. Use /discord status.")

    def _install_signals(self) -> None:
        self._prev = {}
        def on_winch(signum, frame):
            self.events.put(("resize", None))
        def on_term(signum, frame):
            self.events.put(("signal_exit", signum))
        try:
            self._prev[signal.SIGWINCH] = signal.getsignal(signal.SIGWINCH)
            signal.signal(signal.SIGWINCH, on_winch)
        except Exception:
            pass
        for sig in (signal.SIGTERM, signal.SIGHUP):
            try:
                self._prev[sig] = signal.getsignal(sig)
                signal.signal(sig, on_term)
            except Exception:
                pass

    def _restore_signals(self) -> None:
        for sig, prev in getattr(self, "_prev", {}).items():
            try:
                signal.signal(sig, prev)
            except Exception:
                pass

    def _cleanup(self) -> None:
        self._stop = True
        try:
            self.term.write("\033[?2004l")
            self.term.flush()
        except Exception:
            pass
        try:
            self.app.shutdown_integrations()
        except Exception:
            pass
        try:
            self.term.cleanup()
        except Exception:
            pass
        self._restore_signals()

    def _run_plain(self) -> int:
        # Fallback: preserve basic REPL behavior
        print(f"{self.app.config.get('ui',{}).get('name','0rb1t')} v{__version__}")
        while True:
            try:
                line = input("> ")
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print()
                continue
            text = line.strip()
            if not text:
                continue
            if text.startswith("/"):
                res = self.app.dispatch_command(text, session_id=self.session_id)
                if res.exit:
                    return 0
                if res.new_session:
                    self.session_id = None
                if res.message:
                    print(res.message)
                continue
            try:
                resp = self.app.send(text, session_id=self.session_id)
                self.session_id = resp.session_id or self.session_id
                print((resp.text or "").strip() or "(no response)")
            except EngineError as e:
                print(f"error: {e}", file=sys.stderr)

    def loop(self) -> int:
        while not self._stop:
            self._drain_worker_events(render=False)
            self.render()
            ev = self._read_event(timeout=0.1)
            if ev is None:
                continue
            kind, payload = ev
            if kind == "resize":
                self.render()
                continue
            if kind == "signal_exit":
                self.state.add("system", "exiting")
                self.render()
                return 0
            if kind == "key":
                self._handle_key(payload)
                continue
            if kind == "worker":
                self._handle_worker(payload)
                continue
        return 0

    def _drain_worker_events(self, render: bool = True) -> None:
        changed = False
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "worker":
                    self._handle_worker(payload)
                    changed = True
                elif kind == "resize":
                    changed = True
                elif kind == "signal_exit":
                    self._stop = True
                    return
                elif kind == "key":
                    self._handle_key(payload)
                    changed = True
        except queue.Empty:
            pass
        if changed and render:
            self.render()

    def _read_event(self, timeout: float):
        # Prefer queued events
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            pass
        # Read stdin
        try:
            r, _, _ = select.select([sys.stdin], [], [], 0)
        except Exception:
            return None
        if not r:
            return None
        try:
            data = os.read(sys.stdin.fileno(), 4096)
        except BlockingIOError:
            return None
        except Exception:
            return None
        if not data:
            return ("signal_exit", None)
        for ke in self.parser.feed(data):
            self.events.put(("key", ke))
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def _handle_key(self, ke) -> None:
        k = ke.kind
        if k == "paste_start":
            self._paste_mode = True
            self._paste_buf = []
            return
        if k == "paste_end":
            self._paste_mode = False
            if self._paste_buf and not self._busy:
                self.ibuf.insert(''.join(self._paste_buf))
            self._paste_buf = []
            return
        if self._paste_mode:
            if k == "char" and ke.value:
                self._paste_buf.append(ke.value)
            elif k == "enter":
                self._paste_buf.append("\n")
            elif k == "tab":
                self._paste_buf.append("    ")
            return

        if k == "ctrl_c":
            if self._busy:
                self._active_worker_id += 1  # invalidate current result
                self._busy = False
                self.set_status("interrupted", busy=False)
                self.state.add("system", "interrupted. request may continue in engine; result ignored.")
            else:
                self.state.add("system", "use /exit to quit")
            return
        if k == "ctrl_d":
            if not self.ibuf.text.strip():
                self._stop = True
            return
        if k == "ctrl_l":
            return
        if self._busy:
            # Allow scrolling while busy; input is locked.
            if k == "scroll_up":
                self._scroll(-3)
            elif k == "scroll_down":
                self._scroll(3)
            elif k == "page_up":
                self._scroll(-max(3, self.term.size()[1] - 6))
            elif k == "page_down":
                self._scroll(max(3, self.term.size()[1] - 6))
            return

        if k == "enter":
            self._submit()
            return
        if k == "shift_enter":
            self.ibuf.newline()
            return
        if k == "backspace":
            self.ibuf.backspace(); return
        if k == "delete":
            self.ibuf.delete(); return
        if k == "left":
            self.ibuf.left(); return
        if k == "right":
            self.ibuf.right(); return
        if k == "up":
            if self.ibuf.row > 0:
                self.ibuf.up()
            else:
                self._scroll(-1)
            return
        if k == "down":
            if self.ibuf.row < len(self.ibuf.lines) - 1:
                self.ibuf.down()
            else:
                self._scroll(1)
            return
        if k == "home":
            self.ibuf.home(); return
        if k == "end":
            self.ibuf.end(); return
        if k == "ctrl_a":
            self.ibuf.ctrl_a(); return
        if k == "ctrl_e":
            self.ibuf.ctrl_e(); return
        if k == "ctrl_k":
            self.ibuf.kill_to_end(); return
        if k == "ctrl_u":
            self.ibuf.kill_to_start(); return
        if k == "scroll_up":
            self._scroll(-3); return
        if k == "scroll_down":
            self._scroll(3); return
        if k == "page_up":
            self._scroll(-max(3, self.term.size()[1] - 6)); return
        if k == "page_down":
            self._scroll(max(3, self.term.size()[1] - 6)); return
        if k == "char":
            ch = ke.value
            if ch and ch.isprintable():
                self.ibuf.insert(ch)
            return
        if k == "tab":
            self.ibuf.insert("    ")
            return

    def _scroll(self, delta: int) -> None:
        # compute max scroll against current render assumptions
        cols, rows = self.term.size()
        th = self.theme()
        renderer = TUIRenderer(th)
        transcript = renderer.render_transcript(self.state.messages, max(10, cols - 2), version=__version__, engine_name=str(self.app.config.get("engine", {}).get("name", "engine")))
        layout = renderer.layout(cols, rows, self.ibuf)
        vp_h = layout["viewport"]
        max_scroll = max(0, len(transcript) - vp_h)
        if delta == 0:
            return
        # When following and user scrolls up, stop following.
        cur = max_scroll if self.state.follow else self.state.scroll
        nxt = max(0, min(max_scroll, cur + delta))
        self.state.scroll = nxt
        self.state.follow = nxt >= max_scroll

    def _submit(self) -> None:
        text = self.ibuf.text.rstrip("\n")
        if not text.strip():
            self.ibuf.clear()
            return
        # keep command in transcript
        self.state.add("user", text)
        self.ibuf.clear()
        self.state.follow = True

        if text.strip().startswith("/"):
            self._handle_command(text.strip())
            return

        self._start_send(text)

    def _handle_command(self, text: str) -> None:
        try:
            res = self.app.dispatch_command(text, session_id=self.session_id)
        except Exception as e:
            self.state.add("error", f"command error: {e}")
            return
        # apply name/theme changes immediately in UI; app handles discord
        if res.exit:
            if res.message:
                self.state.add("system", res.message)
            self._stop = True
            return
        if res.clear:
            self.state.clear_messages()
            if res.message:
                self.state.add("system", res.message)
            return
        if res.new_session:
            self.session_id = None
            if res.message:
                self.state.add("system", res.message)
            return
        if res.message:
            self.state.add("system" if res.ok else "error", res.message)

    def _start_send(self, text: str) -> None:
        self._busy = True
        self._active_worker_id += 1
        wid = self._active_worker_id
        self.set_status("", busy=True, busy_label=f"{self.app.config.get('ui',{}).get('name','0rb1t')} thinking")

        def work():
            try:
                resp = self.app.send(text, session_id=self.session_id)
                self.events.put(("worker", {"id": wid, "ok": True, "resp": resp}))
            except EngineError as e:
                self.events.put(("worker", {"id": wid, "ok": False, "error": str(e)}))
            except Exception as e:
                self.events.put(("worker", {"id": wid, "ok": False, "error": str(e)}))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _handle_worker(self, payload) -> None:
        if not isinstance(payload, dict):
            return
        wid = payload.get("id")
        if wid != self._active_worker_id:
            return
        self._busy = False
        self.set_status("ready", busy=False)
        if payload.get("ok"):
            resp = payload.get("resp")
            if resp is not None:
                if getattr(resp, "session_id", None):
                    self.session_id = resp.session_id
                out = (getattr(resp, "text", "") or "").strip() or "(no response)"
                self.state.add("assistant", out)
        else:
            self.state.add("error", str(payload.get("error", "unknown error")))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="0rb1t", description="0rb1t - customizable terminal intelligence environment")
    p.add_argument("--version", action="version", version=f"0rb1t {__version__}")
    p.add_argument("--cwd", default=os.getcwd(), help="Working directory for engine/session")
    p.add_argument("--no-alt-screen", action="store_true", help="Do not use terminal alternate screen")
    p.add_argument("--once", metavar="MESSAGE", help="Send one message and print the response")
    p.add_argument("--session", dest="session_id", help="Session ID for --once")
    p.add_argument("message", nargs="*", help="Optional one-shot message (same as --once)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = App(cwd=args.cwd)
    if args.no_alt_screen:
        app.config = {**app.config, "ui": {**app.config.get("ui", {}), "alt_screen": False}}

    oneshot = args.once or (" ".join(args.message).strip() if args.message else None)
    if oneshot:
        return run_once(app, oneshot, session_id=args.session_id)

    tui = ReplTUI(app)
    # no-alt-screen: for now we still use TUI if tty, but can fall back; keep simple.
    if args.no_alt_screen or not bool(app.config.get("ui", {}).get("alt_screen", True)):
        # fallback to plain for --no-alt-screen to honor flag with minimal risk
        return tui._run_plain() if _is_tty() else tui._run_plain()
    return tui.start()


if __name__ == "__main__":
    raise SystemExit(main())
