"""Фикстуры для тестов Echo-Sim."""
import pytest


def minimal_config() -> dict:
    """Минимальный валидный конфиг для тестов."""
    return {
        "epoch": "medieval",
        "narrative_tone": "adventure",
        "llm_model": "llama3",
        "context_size": 5,
        "server_port": 8080,
        "world_tick_interval": "1 hour",
        "skill_growth_rate": 1.0,
        "locations": [
            {
                "id": "tavern",
                "name": "Таверна",
                "atmosphere": "Тепло и шумно",
                "adjacent_location_ids": ["market"]
            },
            {
                "id": "market",
                "name": "Рынок",
                "atmosphere": "Суетливо",
                "adjacent_location_ids": ["tavern"]
            }
        ],
        "player_start": {
            "name": "Герой",
            "health": 100,
            "location_id": "tavern",
            "skills": {"меч": 10, "скрытность": 5},
            "inventory": ["меч", "хлеб"]
        },
        "npcs": [
            {
                "id": "innkeeper",
                "name": "Трактирщик",
                "location_id": "tavern",
                "goals": ["зарабатывать деньги"],
                "memory": [],
                "player_actions_memory": [],
                "schedule": [],
                "status": "alive"
            }
        ],
        "quests": []
    }


def valid_world_config() -> dict:
    """Полный валидный конфиг с несколькими локациями и NPC."""
    return minimal_config()


@pytest.fixture
def config():
    return minimal_config()
