"""Unit-тесты для Engine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import minimal_config
from echo_sim.core.engine import Engine
from echo_sim.core.gm import GameEvent, GMResponse


@pytest.fixture
def engine(tmp_path):
    """Engine с временным конфигом."""
    import json
    cfg_file = tmp_path / "world.json"
    cfg_file.write_text(json.dumps(minimal_config()), encoding="utf-8")
    return Engine(str(cfg_file))


def test_engine_init(engine):
    assert engine.state == "active"
    assert engine.player.name == "Герой"


def test_cmd_look(engine):
    result = engine.process_command("look")
    assert "Таверна" in result


def test_cmd_inventory(engine):
    result = engine.process_command("inventory")
    assert "меч" in result


def test_cmd_status(engine):
    result = engine.process_command("status")
    assert "Герой" in result
    assert "Здоровье" in result


def test_cmd_go_valid(engine):
    result = engine.process_command("go market")
    assert engine.world.current_location_id == "market"


def test_cmd_go_invalid(engine):
    original = engine.world.current_location_id
    result = engine.process_command("go nowhere")
    assert engine.world.current_location_id == original
    assert "не существует" in result


def test_game_over_on_zero_health(engine):
    events = [GameEvent(type="health_change", payload={"delta": -9999})]
    engine.apply_events(events)
    assert engine.state == "game_over"


def test_game_over_blocks_commands(engine):
    engine.state = "game_over"
    result = engine.process_command("look")
    assert "окончена" in result.lower()


def test_restart_resets_state(engine):
    engine.state = "game_over"
    engine.process_command("restart")
    assert engine.state == "active"


def test_apply_skill_growth(engine):
    events = [GameEvent(type="skill_growth", payload={"skill": "меч", "delta": 5})]
    engine.apply_events(events)
    assert engine.player.skills["меч"] == 15


def test_apply_reputation_change(engine):
    events = [GameEvent(type="reputation_change", payload={"target_id": "innkeeper", "delta": 20})]
    engine.apply_events(events)
    assert engine.player.reputation["innkeeper"] == 20


def test_apply_npc_death(engine):
    events = [GameEvent(type="npc_death", payload={"npc_id": "innkeeper"})]
    engine.apply_events(events)
    assert engine.npcs["innkeeper"].status == "dead"


def test_apply_inventory_change(engine):
    events = [GameEvent(type="inventory_change", payload={"add": ["зелье"], "remove": ["хлеб"]})]
    engine.apply_events(events)
    assert "зелье" in engine.player.inventory
    assert "хлеб" not in engine.player.inventory


def test_world_tick_advances_time(engine):
    t0 = engine.world.game_time
    engine.world_tick()
    assert engine.world.game_time > t0


def test_unknown_command_calls_gm(engine):
    with patch.object(engine.gm, 'generate', return_value=GMResponse(narrative="Ответ GM", events=[])) as mock_gen:
        result = engine.process_command("прыгаю через забор")
        mock_gen.assert_called_once()
        assert "Ответ GM" in result


def test_get_full_state_serializable(engine):
    import json
    state = engine.get_full_state()
    json.dumps(state)
