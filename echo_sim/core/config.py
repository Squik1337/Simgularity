"""Загрузка и валидация конфигурации мира."""
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = ["epoch", "locations", "narrative_tone", "player_start"]


def load_config(path: str = "echo_sim/config/world.json") -> dict:
    """Загрузить и валидировать конфиг из JSON-файла."""
    config_path = Path(path)
    if not config_path.exists():
        sys.exit(f"Ошибка: файл конфигурации не найден: {path}")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"Ошибка: невалидный JSON в файле конфигурации {path}: {e}")
    except OSError as e:
        sys.exit(f"Ошибка чтения файла конфигурации {path}: {e}")

    missing = [field for field in REQUIRED_FIELDS if field not in config]
    if missing:
        sys.exit(f"Ошибка: в конфигурации отсутствуют обязательные поля: {', '.join(missing)}")

    # Значения по умолчанию
    config.setdefault("llm_model", "llama3")
    config.setdefault("context_size", 20)
    config.setdefault("server_port", 8080)
    config.setdefault("world_tick_interval", "1 hour")
    config.setdefault("skill_growth_rate", 1.0)
    config.setdefault("npcs", [])
    config.setdefault("quests", [])

    return config
