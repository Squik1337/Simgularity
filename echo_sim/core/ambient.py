"""Генератор фоновых событий — GM сам придумывает что происходит."""
from __future__ import annotations
import random
from dataclasses import dataclass


@dataclass
class AmbientTrigger:
    """Минимальный контекст для GM — что генерировать."""
    kind: str        # "detail" | "encounter" | "sound" | "weather"
    intensity: str   # "subtle" | "noticeable" | "striking"
    location_id: str


def roll_ambient(location_id: str, game_time: int, last_ambient_tick: int) -> AmbientTrigger | None:
    """
    Решить — происходит ли что-то фоновое прямо сейчас.
    ~25% шанс на тик, минимум 2 тика (120 мин) между событиями.
    """
    if game_time - last_ambient_tick < 120:
        return None
    if random.random() > 0.28:
        return None

    kind = random.choices(
        ["detail", "encounter", "sound", "weather"],
        weights=[40, 30, 20, 10],
    )[0]

    intensity = random.choices(
        ["subtle", "noticeable", "striking"],
        weights=[60, 30, 10],
    )[0]

    return AmbientTrigger(kind=kind, intensity=intensity, location_id=location_id)
