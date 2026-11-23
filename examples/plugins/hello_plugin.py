"""Example 0rb1t plugin.

Drop into ~/.config/0rb1t/plugins/ or .0rb1t/plugins/
"""

from types import SimpleNamespace


def register(api, ctx):
    def hello(args, command_ctx):
        who = " ".join(args) if args else "world"
        return SimpleNamespace(ok=True, message=f"hello, {who}", clear=False, exit=False, new_session=False)

    api.register_command("hello", hello, help="Say hello from a plugin")
