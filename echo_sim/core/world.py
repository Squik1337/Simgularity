"""Состояние мира: эпоха, локации, события."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from echo_sim.core.npc import NPC

MAX_EVENT_LOG = 50


@dataclass
class WorldEvent:
    id: str
    description: str
    affected_location_id: str
    timestamp: int
    event_type: str  # "npc_death" | "world_change" | "npc_action" | "rumor"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "affected_location_id": self.affected_location_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
        }


@dataclass
class Location:
    id: str
    name: str
    atmosphere: str
    adjacent_location_ids: list[str] = field(default_factory=list)
    events: list[WorldEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "atmosphere": self.atmosphere,
            "adjacent_location_ids": self.adjacent_location_ids,
            "events": [e.to_dict() for e in self.events[-5:]],
        }


class World:
    def __init__(self, config: dict) -> None:
        self.epoch: str = config["epoch"]
        self.game_time: int = 0  # минуты от начала игры
        self.event_log: list[WorldEvent] = []
        self._event_counter: int = 0

        self.locations: dict[str, Location] = {}
        for loc_data in config.get("locations", []):
            loc = Location(
                id=loc_data["id"],
                name=loc_data["name"],
                atmosphere=loc_data["atmosphere"],
                adjacent_location_ids=loc_data.get("adjacent_location_ids", []),
            )
            self.locations[loc.id] = loc

        start_loc = config.get("player_start", {}).get("location_id", "")
        if start_loc and start_loc in self.locations:
            self.current_location_id: str = start_loc
        elif self.locations:
            self.current_location_id = next(iter(self.locations))
        else:
            self.current_location_id = ""

    def move_player(self, location_id: str) -> bool:
        """Переместить игрока. Возвращает True при успехе."""
        if location_id not in self.locations:
            return False
        self.current_location_id = location_id
        return True

    def add_event(self, event: WorldEvent) -> None:
        """Добавить мировое событие в лог и в локацию."""
        self.event_log.append(event)
        if len(self.event_log) > MAX_EVENT_LOG:
            self.event_log = self.event_log[-MAX_EVENT_LOG:]
        if event.affected_location_id in self.locations:
            self.locations[event.affected_location_id].events.append(event)

    def new_event(self, description: str, location_id: str, event_type: str = "world_change") -> WorldEvent:
        """Создать и добавить новое событие."""
        self._event_counter += 1
        event = WorldEvent(
            id=f"evt_{self._event_counter}",
            description=description,
            affected_location_id=location_id,
            timestamp=self.game_time,
            event_type=event_type,
        )
        self.add_event(event)
        return event

    def get_adjacent_npcs(self, location_id: str, all_npcs: dict) -> list:
        """Получить NPC из соседних локаций."""
        if location_id not in self.locations:
            return []
        adjacent_ids = self.locations[location_id].adjacent_location_ids
        return [
            npc for npc in all_npcs.values()
            if npc.location_id in adjacent_ids and npc.status == "alive"
        ]

    def get_scene_context(self, npcs: dict) -> dict:
        """Контекст текущей сцены для GM."""
        loc = self.locations.get(self.current_location_id)
        if not loc:
            return {}
        scene_npcs = [
            npc.get_context() for npc in npcs.values()
            if npc.location_id == self.current_location_id and npc.status == "alive"
        ]
        return {
            "location": loc.to_dict(),
            "game_time": self._format_time(),
            "npcs_present": scene_npcs,
            "recent_events": [e.to_dict() for e in loc.events[-3:]],
        }

    def _format_time(self) -> str:
        hours = (self.game_time // 60) % 24
        minutes = self.game_time % 60
        return f"{hours:02d}:{minutes:02d}"

    def get_state(self) -> dict:
        return {
            "epoch": self.epoch,
            "current_location_id": self.current_location_id,
            "game_time": self.game_time,
            "game_time_formatted": self._format_time(),
            "locations": {lid: loc.to_dict() for lid, loc in self.locations.items()},
            "event_log": [e.to_dict() for e in self.event_log],
        }
