"""Unit-тесты для TUI (без запуска полного Textual приложения)."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import MagicMock, patch
from tests.conftest import minimal_config


def make_engine(tmp_path):
    from echo_sim.core.engine import Engine
    cfg_file = tmp_path / "world.json"
    cfg_file.write_text(json.dumps(minimal_config()), encoding="utf-8")
    return Engine(str(cfg_file))


@pytest.fixture
def engine(tmp_path):
    return make_engine(tmp_path)


def test_tui_import():
    """TUI должен импортироваться без ошибок."""
    try:
        from echo_sim.tui import EchoSimApp, StatusPanel, EPOCH_THEMES
        assert EchoSimApp is not None
    except ImportError as e:
        pytest.skip(f"textual не установлен: {e}")


def test_epoch_themes_coverage():
    """Все основные эпохи должны иметь тему."""
    try:
        from echo_sim.tui import EPOCH_THEMES
    except ImportError:
        pytest.skip("textual не установлен")
    for epoch in ["post-apocalyptic", "cyberpunk", "medieval", "fantasy", "modern"]:
        assert epoch in EPOCH_THEMES, f"Эпоха '{epoch}' не имеет темы"


def test_status_panel_hp_bar():
    """HP-бар должен корректно отображать здоровье."""
    try:
        from echo_sim.tui import StatusPanel
    except ImportError:
        pytest.skip("textual не установлен")
    bar = StatusPanel._hp_bar(50, 100, width=8)
    assert len(bar) == 8
    assert bar.count("█") == 4
    assert bar.count("░") == 4


def test_status_panel_hp_bar_full():
    try:
        from echo_sim.tui import StatusPanel
    except ImportError:
        pytest.skip("textual не установлен")
    bar = StatusPanel._hp_bar(100, 100, width=8)
    assert "░" not in bar


def test_status_panel_hp_bar_empty():
    try:
        from echo_sim.tui import StatusPanel
    except ImportError:
        pytest.skip("textual не установлен")
    bar = StatusPanel._hp_bar(0, 100, width=8)
    assert "█" not in bar


def test_engine_process_command_passthrough(engine):
    """Engine.process_command должен принимать команду без изменений."""
    result = engine.process_command("look")
    assert isinstance(result, str)
    assert len(result) > 0


def test_engine_game_over_blocks_input(engine):
    """При game_over Engine блокирует команды."""
    engine.state = "game_over"
    result = engine.process_command("look")
    assert "окончена" in result.lower()


def test_engine_game_over_allows_restart(engine):
    """При game_over Engine принимает restart."""
    engine.state = "game_over"
    result = engine.process_command("restart")
    assert engine.state == "active"
