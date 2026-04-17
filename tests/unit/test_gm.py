"""Unit-тесты для GameMaster."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from tests.conftest import minimal_config
from echo_sim.core.gm import GameMaster, GMResponse, GameEvent


@pytest.fixture
def gm():
    return GameMaster(minimal_config())


def make_world_ctx(config=None):
    cfg = config or minimal_config()
    return {
        "location": {"id": "tavern", "name": "Таверна", "atmosphere": "Тепло"},
        "game_time": "08:00",
        "player": {
            "name": "Герой", "health": 100, "max_health": 100,
            "skills": {"меч": 10}, "inventory": ["меч"],
        },
        "npcs_present": [],
        "active_quests": [],
        "recent_events": [],
        "reputation_context": {},
    }


def test_parse_valid_json(gm):
    raw = '{"narrative": "Ты входишь в таверну.", "events": []}'
    result = gm._parse_response(raw)
    assert result.narrative == "Ты входишь в таверну."
    assert result.events == []


def test_parse_json_with_events(gm):
    raw = '{"narrative": "Ты ударил.", "events": [{"type": "health_change", "payload": {"delta": -10}}]}'
    result = gm._parse_response(raw)
    assert len(result.events) == 1
    assert result.events[0].type == "health_change"
    assert result.events[0].payload["delta"] == -10


def test_parse_invalid_json_graceful(gm):
    raw = "Это просто текст без JSON"
    result = gm._parse_response(raw)
    assert result.narrative == raw
    assert result.events == []


def test_parse_json_embedded_in_text(gm):
    raw = 'Вот ответ: {"narrative": "Нарратив", "events": []} конец'
    result = gm._parse_response(raw)
    assert result.narrative == "Нарратив"


def test_build_system_prompt_contains_epoch(gm):
    ctx = make_world_ctx()
    prompt = gm._build_system_prompt(ctx)
    assert "medieval" in prompt


def test_build_system_prompt_contains_location(gm):
    ctx = make_world_ctx()
    prompt = gm._build_system_prompt(ctx)
    assert "Таверна" in prompt


def test_build_system_prompt_contains_player_name(gm):
    ctx = make_world_ctx()
    prompt = gm._build_system_prompt(ctx)
    assert "Герой" in prompt


def test_build_system_prompt_contains_skills(gm):
    ctx = make_world_ctx()
    prompt = gm._build_system_prompt(ctx)
    assert "меч" in prompt


def test_tone_adventure_in_prompt(gm):
    ctx = make_world_ctx()
    prompt = gm._build_system_prompt(ctx)
    assert "героизм" in prompt.lower() or "adventure" in prompt.lower() or "эпическ" in prompt.lower()


def test_tone_hardcore_different_from_adventure():
    cfg = minimal_config()
    cfg["narrative_tone"] = "hardcore"
    gm_hardcore = GameMaster(cfg)
    cfg2 = minimal_config()
    cfg2["narrative_tone"] = "adventure"
    gm_adventure = GameMaster(cfg2)
    ctx = make_world_ctx()
    prompt_h = gm_hardcore._build_system_prompt(ctx)
    prompt_a = gm_adventure._build_system_prompt(ctx)
    assert prompt_h != prompt_a


def test_build_messages_context_limit(gm):
    # Заполнить контекст сверх лимита
    for i in range(30):
        gm.session_context.append({"role": "user", "content": f"команда {i}"})
        gm.session_context.append({"role": "assistant", "content": f"ответ {i}"})
    messages = gm._build_messages("новая команда")
    # Последнее сообщение — новая команда
    assert messages[-1]["content"] == "новая команда"
    # Контекст не превышает лимит * 2 + 1 (новое сообщение)
    assert len(messages) <= gm.context_window * 2 + 1
