# -*- coding: utf-8 -*-
"""NPC с памятью, целями и расписанием."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from echo_sim.core.gm import GameMaster
    from echo_sim.core.world import World, WorldEvent

MAX_MEMORY = 15
MAX_PLAYER_ACTIONS = 30


@dataclass
class ScheduleEntry:
    time_range: tuple[int, int]
    location_id: str


@dataclass
class MemoryEntry:
    """Запись в памяти NPC с весом важности."""
    text: str
    weight: int = 1   # 1=обычное, 2=важное, 3=критическое (убийство, предательство)
    about_player: bool = False  # касается ли игрока напрямую

    def __str__(self) -> str:
        prefix = "!!!" if self.weight >= 3 else ("!!" if self.weight >= 2 else "")
        return f"{prefix}{self.text}" if prefix else self.text


class NPC:
    def __init__(self, data: dict) -> None:
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.location_id: str = data.get("location_id", "")
        self.goals: list[str] = list(data.get("goals", []))
        self.appearance: str = data.get("appearance", "")
        self.profession: str = data.get("profession", "")
        self.status: str = data.get("status", "alive")

        # Память — список MemoryEntry (или строк для обратной совместимости)
        self._memory: list[MemoryEntry] = []
        for m in data.get("memory", []):
            if isinstance(m, dict):
                self._memory.append(MemoryEntry(**m))
            else:
                self._memory.append(MemoryEntry(text=str(m)))
        self._memory = self._memory[-MAX_MEMORY:]

        self.player_actions_memory: list[str] = list(data.get("player_actions_memory", []))[-MAX_PLAYER_ACTIONS:]

        self.schedule: list[ScheduleEntry] = []
        for entry in data.get("schedule", []):
            tr = entry.get("time_range", [0, 1440])
            self.schedule.append(ScheduleEntry(
                time_range=(tr[0], tr[1]),
                location_id=entry["location_id"],
            ))

    # ── Память ────────────────────────────────────────────

    @property
    def memory(self) -> list[str]:
        """Строковое представление памяти для промпта."""
        return [str(m) for m in self._memory]

    def add_memory(self, text: str, weight: int = 1, about_player: bool = False) -> None:
        self._memory.append(MemoryEntry(text=text, weight=weight, about_player=about_player))
        # Критические записи не вытесняются обычными — сортируем по весу при обрезке
        if len(self._memory) > MAX_MEMORY:
            # Оставляем все критические + самые свежие обычные
            critical = [m for m in self._memory if m.weight >= 3]
            rest = [m for m in self._memory if m.weight < 3]
            rest = rest[-(MAX_MEMORY - len(critical)):]
            self._memory = critical + rest

    def add_player_action(self, action: str) -> None:
        self.player_actions_memory.append(action)
        if len(self.player_actions_memory) > MAX_PLAYER_ACTIONS:
            self.player_actions_memory = self.player_actions_memory[-MAX_PLAYER_ACTIONS:]

    def witnessed_player_action(self, description: str, weight: int = 1) -> None:
        """NPC стал свидетелем действия игрока."""
        self.add_memory(f"[Видел] {description}", weight=weight, about_player=True)
        self.add_player_action(description)

    def heard_rumor(self, description: str) -> None:
        """NPC услышал слух о действии игрока."""
        self.add_memory(f"[Слух] {description}", weight=1, about_player=True)

    # ── Обновление ────────────────────────────────────────

    def update(self, game_time: int, gm: Optional[GameMaster], world: Optional[World]) -> Optional[WorldEvent]:
        if self.status != "alive":
            return None

        day_time = game_time % 1440
        moved = False
        for entry in self.schedule:
            start, end = entry.time_range
            if start <= day_time < end:
                if self.location_id != entry.location_id:
                    self.location_id = entry.location_id
                    moved = True
                break

        if moved and world:
            from echo_sim.core.world import WorldEvent as WE
            evt = WE(
                id=f"move_{self.id}_{game_time}",
                description=f"{self.name} сменил местонахождение",
                affected_location_id=self.location_id,
                timestamp=game_time,
                event_type="npc_action",
            )
            world.add_event(evt)
            return evt

        return None

    # ── Контекст для GM ───────────────────────────────────

    def get_context(self) -> dict:
        # Для промпта — сначала критические записи, потом свежие
        critical = [str(m) for m in self._memory if m.weight >= 3]
        recent = [str(m) for m in self._memory if m.weight < 3][-5:]
        memory_for_prompt = critical + recent

        return {
            "id": self.id,
            "name": self.name,
            "location_id": self.location_id,
            "goals": self.goals,
            "appearance": self.appearance,
            "profession": self.profession,
            "memory": memory_for_prompt,
            "player_actions_memory": self.player_actions_memory[-10:],
            "status": self.status,
        }

    def get_state(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "location_id": self.location_id,
            "goals": self.goals,
            "appearance": self.appearance,
            "profession": self.profession,
            "memory": [{"text": m.text, "weight": m.weight, "about_player": m.about_player}
                       for m in self._memory],
            "player_actions_memory": list(self.player_actions_memory),
            "status": self.status,
            "schedule": [
                {"time_range": list(e.time_range), "location_id": e.location_id}
                for e in self.schedule
            ],
        }
