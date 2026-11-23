from pathlib import Path

from orb1t.plugins.loader import PluginContext, PluginManager


def test_plugin_load_and_command(tmp_path: Path):
    plugin = tmp_path / "hello.py"
    plugin.write_text(
        "def register(api, ctx):\n"
        "    api.register_command('hello', lambda args, ctx: type('R', (), {'ok':True,'message':'hi','clear':False,'exit':False,'new_session':False})(), help='say hi')\n",
        encoding="utf-8",
    )
    pm = PluginManager()
    ctx = PluginContext(app_version="0.0.0", config={}, data_dir=tmp_path, cwd=tmp_path)
    pm.load_from_paths([tmp_path], ctx)
    spec = pm.resolve_command("hello")
    assert spec is not None
    res = spec.handler([], {})
    assert res.message == "hi"
