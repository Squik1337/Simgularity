"""Unit-тесты для Player."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from tests.conftest import minimal_config
from echo_sim.core.player import Player, Quest


@pytest.fixture
def player():
    return Player(minimal_config())


def test_player_init_name(player):
    assert player.name == "Герой"


def test_player_init_health(player):
    assert player.health == 100


def test_player_init_skills(player):
    assert "меч" in player.skills
    assert player.skills["меч"] == 10


def test_player_init_inventory(player):
    assert "меч" in player.inventory


def test_health_change_positive(player):
    player.apply_health_change(-30)
    assert player.health == 70


def test_health_change_floor_zero(player):
    player.apply_health_change(-200)
    assert player.health == 0


def test_health_never_negative(player):
    player.apply_health_change(-9999)
    assert player.health >= 0


def test_skill_growth_capped_at_100(player):
    player.skills["меч"] = 95
    player.apply_skill_growth("меч", 20)
    assert player.skills["меч"] == 100


def test_skill_growth_new_skill(player):
    player.apply_skill_growth("магия", 5)
    assert player.skills["магия"] == 6  # 1 + 5


def test_reputation_clamped_max(player):
    player.apply_reputation_change("innkeeper", 200)
    assert player.reputation["innkeeper"] == 100


def test_reputation_clamped_min(player):
    player.apply_reputation_change("innkeeper", -200)
    assert player.reputation["innkeeper"] == -100


def test_add_quest(player):
    q = Quest(id="q1", title="Тест", description="Описание", giver_npc_id="innkeeper")
    player.add_quest(q)
    assert any(quest.id == "q1" for quest in player.active_quests)


def test_quest_status_update(player):
    q = Quest(id="q1", title="Тест", description="Описание", giver_npc_id="innkeeper")
    player.add_quest(q)
    result = player.update_quest_status("q1", "in_progress")
    assert result is True
    assert player.active_quests[0].status == "in_progress"


def test_quest_terminal_status_immutable(player):
    q = Quest(id="q1", title="Тест", description="Описание", giver_npc_id="innkeeper", status="completed")
    player.add_quest(q)
    result = player.update_quest_status("q1", "failed")
    assert result is False
    assert player.active_quests[0].status == "completed"


def test_get_state_serializable(player):
    state = player.get_state()
    json.dumps(state)
