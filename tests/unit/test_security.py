"""Тесты безопасности: ограничение путей сохранений и загрузка ключа из окружения."""
import os

from echo_sim.core.engine import resolve_save_path, SAVE_DIR
from echo_sim.core.config import load_config


def _base():
    return os.path.abspath(SAVE_DIR)


def test_resolve_save_path_stays_in_save_dir():
    for attack in ["../../etc/passwd", "/etc/passwd", "../secret", "a/b/c.json"]:
        resolved = resolve_save_path(attack)
        assert os.path.commonpath([_base(), resolved]) == _base()


def test_resolve_save_path_forces_json_extension():
    assert resolve_save_path("foo").endswith("foo.json")
    assert resolve_save_path("").endswith("savegame.json")


def test_api_key_read_from_env(tmp_path, monkeypatch):
    import json
    from tests.conftest import minimal_config

    cfg = minimal_config()
    cfg["api_key"] = ""
    cfg_file = tmp_path / "world.json"
    cfg_file.write_text(json.dumps(cfg), encoding="utf-8")

    monkeypatch.setenv("ECHOSIM_API_KEY", "env-secret-123")
    loaded = load_config(str(cfg_file))
    assert loaded["api_key"] == "env-secret-123"
