"""Unit-тесты для NPC."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from echo_sim.core.npc import NPC, MAX_MEMORY, MAX_PLAYER_ACTIONS


def make_npc(location_id="tavern", schedule=None):
    data = {
        "id": "test_npc",
        "name": "Тестовый NPC",
        "location_id": location_id,
        "goals": ["цель 1"],
        "memory": [],
        "player_actions_memory": [],
        "status": "alive",
        "schedule": schedule or [],
    }
    return NPC(data)


def test_npc_init():
    npc = make_npc()
    assert npc.id == "test_npc"
    assert npc.status == "alive"


def test_add_memory_basic():
    npc = make_npc()
    npc.add_memory("событие 1")
    assert "событие 1" in npc.memory


def test_add_memory_limit():
    npc = make_npc()
    for i in range(15):
        npc.add_memory(f"событие {i}")
    assert len(npc.memory) == MAX_MEMORY
    assert npc.memory[-1] == "событие 14"


def test_add_player_action_limit():
    npc = make_npc()
    for i in range(25):
        npc.add_player_action(f"действие {i}")
    assert len(npc.player_actions_memory) == MAX_PLAYER_ACTIONS


def test_update_schedule_moves_npc():
    schedule = [{"time_range": [0, 480], "location_id": "market"}]
    npc = make_npc(location_id="tavern", schedule=schedule)
    npc.update(game_time=120, gm=None, world=None)
    assert npc.location_id == "market"


def test_update_schedule_no_match():
    schedule = [{"time_range": [600, 1200], "location_id": "market"}]
    npc = make_npc(location_id="tavern", schedule=schedule)
    npc.update(game_time=120, gm=None, world=None)
    assert npc.location_id == "tavern"


def test_dead_npc_does_not_move():
    schedule = [{"time_range": [0, 1440], "location_id": "market"}]
    npc = make_npc(location_id="tavern", schedule=schedule)
    npc.status = "dead"
    npc.update(game_time=120, gm=None, world=None)
    assert npc.location_id == "tavern"


def test_get_state_serializable():
    npc = make_npc()
    state = npc.get_state()
    json.dumps(state)
