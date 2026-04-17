# -*- coding: utf-8 -*-
"""Персонаж игрока: навыки, инвентарь, репутация, квесты, память."""
from __future__ import annotations
from dataclasses import dataclass, field

VALID_QUEST_STATUSES = {"accepted", "in_progress", "completed", "failed"}
TERMINAL_QUEST_STATUSES = {"completed", "failed"}
MAX_JOURNAL = 50       # записей в журнале
MAX_MAP_NOTES = 30     # меток на ментальной карте
MAX_ACQUAINTANCES = 40 # знакомств


@dataclass
class Quest:
    id: str
    title: str
    description: str
    giver_npc_id: str
    status: str = "accepted"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "giver_npc_id": self.giver_npc_id,
            "status": self.status,
        }


@dataclass
class JournalEntry:
    """Запись в дневнике игрока."""
    text: str
    location_id: str
    game_time: int
    important: bool = False  # важные события не вытесняются

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "location_id": self.location_id,
            "game_time": self.game_time,
            "important": self.important,
        }


@dataclass
class MapNote:
    """Метка на ментальной карте игрока."""
    location_id: str
    label: str          # "здесь был гоблин", "видел башню", "логово бандитов"
    game_time: int
    visited: bool = True

    def to_dict(self) -> dict:
        return {
            "location_id": self.location_id,
            "label": self.label,
            "game_time": self.game_time,
            "visited": self.visited,
        }


@dataclass
class Acquaintance:
    """Знакомый персонаж — кого встретил и что о нём знает."""
    npc_id: str
    name: str
    description: str    # внешность, профессия, первое впечатление
    last_location_id: str
    notes: list[str] = field(default_factory=list)  # что узнал о нём

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "description": self.description,
            "last_location_id": self.last_location_id,
            "notes": list(self.notes),
        }


class Player:
    def __init__(self, config: dict) -> None:
        ps = config.get("player_start", {})
        self.name: str = ps.get("name", "Герой")
        self.health: int = ps.get("health", 100)
        self.max_health: int = ps.get("health", 100)

        raw_skills = ps.get("skills", {})
        if isinstance(raw_skills, list):
            self.skills: dict[str, int] = {s: 1 for s in raw_skills}
        else:
            self.skills = {k: max(1, min(100, int(v))) for k, v in raw_skills.items()}

        self.inventory: list[str] = list(ps.get("inventory", []))
        self.reputation: dict[str, int] = {}
        self.active_quests: list[Quest] = []

        # Экипировка
        self.equipped: dict[str, str] = {
            "weapon": "",
            "armor": "",
            "offhand": "",
        }

        # Память игрока
        self.journal: list[JournalEntry] = []
        self.map_notes: list[MapNote] = []
        self.acquaintances: dict[str, Acquaintance] = {}

    # ── Здоровье и навыки ─────────────────────────────────

    def apply_health_change(self, delta: int) -> None:
        self.health = max(0, self.health + delta)

    def apply_skill_growth(self, skill: str, delta: int) -> None:
        current = self.skills.get(skill, 1)
        self.skills[skill] = min(100, max(1, current + delta))

    def apply_reputation_change(self, target_id: str, delta: int) -> None:
        current = self.reputation.get(target_id, 0)
        self.reputation[target_id] = max(-100, min(100, current + delta))

    # ── Квесты ────────────────────────────────────────────

    def add_quest(self, quest: Quest) -> None:
        if not any(q.id == quest.id for q in self.active_quests):
            self.active_quests.append(quest)

    def update_quest_status(self, quest_id: str, status: str) -> bool:
        if status not in VALID_QUEST_STATUSES:
            return False
        for quest in self.active_quests:
            if quest.id == quest_id:
                if quest.status in TERMINAL_QUEST_STATUSES:
                    return False
                quest.status = status
                return True
        return False

    # ── Инвентарь ─────────────────────────────────────────

    def add_inventory_item(self, item: str) -> None:
        self.inventory.append(item)

    def remove_inventory_item(self, item: str) -> bool:
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False

    def equip(self, item: str) -> str:
        """Экипировать предмет. Возвращает сообщение."""
        item_lower = item.lower()
        # Определяем слот
        if any(w in item_lower for w in ("меч", "кинжал", "топор", "дубина", "копьё", "лук", "посох")):
            slot = "weapon"
        elif any(w in item_lower for w in ("броня", "кольчуга", "доспех", "куртка", "щит")):
            slot = "armor" if "щит" not in item_lower else "offhand"
        elif any(w in item_lower for w in ("щит", "факел", "фонарь")):
            slot = "offhand"
        else:
            return f"Не знаю как экипировать '{item}'."

        if item not in self.inventory:
            return f"'{item}' нет в инвентаре."

        old = self.equipped.get(slot, "")
        self.equipped[slot] = item
        if old:
            return f"Снял '{old}', надел '{item}'."
        return f"Экипировано: {item}."

    def unequip(self, slot: str) -> str:
        item = self.equipped.get(slot, "")
        if not item:
            return f"Слот '{slot}' пуст."
        self.equipped[slot] = ""
        return f"Снято: {item}."

    def get_equipped_bonus(self) -> dict:
        """Бонусы от экипировки к навыкам."""
        bonuses = {"меч": 0, "защита": 0}
        weapon = self.equipped.get("weapon", "").lower()
        armor = self.equipped.get("armor", "").lower()
        if "длинный меч" in weapon:
            bonuses["меч"] += 5
        elif "кинжал" in weapon:
            bonuses["меч"] += 2
        elif "короткий меч" in weapon:
            bonuses["меч"] += 3
        if "кольчуга" in armor:
            bonuses["защита"] += 8
        elif "кожаная броня" in armor or "кожаная куртка" in armor:
            bonuses["защита"] += 4
        if self.equipped.get("offhand", ""):
            bonuses["защита"] += 3
        return bonuses

    # ── Журнал ────────────────────────────────────────────

    def add_journal_entry(self, text: str, location_id: str, game_time: int, important: bool = False) -> None:
        entry = JournalEntry(text=text, location_id=location_id, game_time=game_time, important=important)
        self.journal.append(entry)
        if len(self.journal) > MAX_JOURNAL:
            # Вытесняем только неважные записи
            non_important = [e for e in self.journal if not e.important]
            important_entries = [e for e in self.journal if e.important]
            if non_important:
                non_important = non_important[-(MAX_JOURNAL - len(important_entries)):]
            self.journal = important_entries + non_important

    def get_recent_journal(self, n: int = 5) -> list[str]:
        """Последние N записей для промпта GM."""
        return [e.text for e in self.journal[-n:]]

    # ── Ментальная карта ──────────────────────────────────

    def add_map_note(self, location_id: str, label: str, game_time: int) -> None:
        # Обновляем если метка для этой локации уже есть
        for note in self.map_notes:
            if note.location_id == location_id and note.label == label:
                note.game_time = game_time
                return
        self.map_notes.append(MapNote(location_id=location_id, label=label, game_time=game_time))
        if len(self.map_notes) > MAX_MAP_NOTES:
            self.map_notes = self.map_notes[-MAX_MAP_NOTES:]

    def mark_visited(self, location_id: str, game_time: int) -> None:
        """Отметить локацию как посещённую."""
        for note in self.map_notes:
            if note.location_id == location_id:
                note.visited = True
                return
        # Первое посещение — просто отмечаем
        self.map_notes.append(MapNote(
            location_id=location_id,
            label="был здесь",
            game_time=game_time,
            visited=True,
        ))

    def get_map_notes_for_location(self, location_id: str) -> list[str]:
        return [n.label for n in self.map_notes if n.location_id == location_id]

    def get_all_map_notes_summary(self) -> str:
        """Краткая сводка ментальной карты для промпта."""
        if not self.map_notes:
            return ""
        lines = []
        seen = set()
        for note in self.map_notes:
            if note.label != "был здесь" and note.location_id not in seen:
                lines.append(f"{note.location_id}: {note.label}")
                seen.add(note.location_id)
        return "; ".join(lines[:10])

    # ── Знакомства ────────────────────────────────────────

    def meet_npc(self, npc_id: str, name: str, description: str, location_id: str) -> None:
        """Познакомиться с NPC."""
        if npc_id in self.acquaintances:
            # Обновляем последнее местонахождение
            self.acquaintances[npc_id].last_location_id = location_id
        else:
            self.acquaintances[npc_id] = Acquaintance(
                npc_id=npc_id,
                name=name,
                description=description,
                last_location_id=location_id,
            )

    def add_npc_note(self, npc_id: str, note: str) -> None:
        """Добавить заметку о знакомом NPC."""
        if npc_id in self.acquaintances:
            acq = self.acquaintances[npc_id]
            if note not in acq.notes:
                acq.notes.append(note)
                if len(acq.notes) > 10:
                    acq.notes = acq.notes[-10:]

    def get_acquaintance_summary(self) -> str:
        """Краткий список знакомых для промпта."""
        if not self.acquaintances:
            return ""
        return ", ".join(
            f"{a.name} ({a.description[:30]})"
            for a in list(self.acquaintances.values())[:8]
        )

    # ── Состояние ─────────────────────────────────────────

    def get_state(self) -> dict:
        return {
            "name": self.name,
            "health": self.health,
            "max_health": self.max_health,
            "skills": dict(self.skills),
            "inventory": list(self.inventory),
            "equipped": dict(self.equipped),
            "reputation": dict(self.reputation),
            "active_quests": [q.to_dict() for q in self.active_quests],
            "journal": [e.to_dict() for e in self.journal[-10:]],
            "map_notes": [n.to_dict() for n in self.map_notes],
            "acquaintances": {k: v.to_dict() for k, v in self.acquaintances.items()},
        }
