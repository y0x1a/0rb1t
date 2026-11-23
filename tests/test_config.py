from pathlib import Path

from orb1t.config import (
    DEFAULT_CONFIG,
    deep_merge,
    get_path,
    migrate_config,
    parse_value,
    set_path,
    validate_config,
)


def test_migrate_old_theme_name():
    old = {"theme": "cyan", "name": "Nova"}
    migrated = migrate_config(old)
    assert migrated["ui"]["theme"] == "cyan"
    assert migrated["ui"]["name"] == "Nova"


def test_set_get_path():
    cfg = deep_merge(DEFAULT_CONFIG, {})
    cfg2 = set_path(cfg, "ui.theme", "green")
    assert get_path(cfg2, "ui.theme") == "green"


def test_parse_value():
    assert parse_value("true") is True
    assert parse_value("false") is False
    assert parse_value("null") is None
    assert parse_value("42") == 42
    assert parse_value("[1,2]") == [1, 2]
    assert parse_value("hello") == "hello"


def test_validate_default():
    assert validate_config(DEFAULT_CONFIG) == []
