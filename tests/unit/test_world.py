"""Unit-тесты для World."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from tests.conftest import minimal_config
from echo_sim.core.world import World, WorldEvent


@pytest.fixture
def world():
    return World(minimal_config())


def test_world_init_locations(world):
    assert "tavern" in world.locations
    assert "market" in world.locations


def test_world_initial_location(world):
    assert world.current_location_id == "tavern"


def test_move_player_valid(world):
    result = world.move_player("market")
    assert result is True
    assert world.current_location_id == "market"


def test_move_player_invalid(world):
    original = world.current_location_id
    result = world.move_player("nonexistent_place")
    assert result is False
    assert world.current_location_id == original


def test_add_event_appends_to_log(world):
    event = WorldEvent(
        id="e1", description="Тест", affected_location_id="tavern",
        timestamp=0, event_type="world_change"
    )
    world.add_event(event)
    assert event in world.event_log


def test_event_log_max_50(world):
    for i in range(60):
        world.new_event(f"Событие {i}", "tavern")
    assert len(world.event_log) <= 50


def test_get_state_serializable(world):
    state = world.get_state()
    json.dumps(state)  # не должно бросать исключение


def test_get_state_contains_epoch(world):
    state = world.get_state()
    assert state["epoch"] == "medieval"


def test_get_scene_context(world):
    ctx = world.get_scene_context({})
    assert "location" in ctx
    assert ctx["location"]["id"] == "tavern"
