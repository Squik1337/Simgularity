# -*- coding: utf-8 -*-
"""Система кубика d20 — классификация действий, броски, исходы."""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from echo_sim.core.player import Player
    from echo_sim.core.npc import NPC

# ── Исходы ────────────────────────────────────────────────

OUTCOME_RU = {
    "critical_success": "Критический успех",
    "success": "Успех",
    "failure": "Провал",
    "critical_failure": "Критический провал",
}

OUTCOME_INSTRUCTIONS = {
    "critical_success": (
        "Действие удалось МАКСИМАЛЬНО — без сопротивления, с дополнительным эффектом. "
        "Если это ограбление — верни inventory_change с предметами цели. "
        "Если это насилие — цель не может сопротивляться."
    ),
    "success": (
        "Действие удалось. Цель подчиняется или не успевает помешать. "
        "Если это ограбление — верни inventory_change с частью предметов цели."
    ),
    "failure": (
        "Действие провалилось. Цель сопротивляется, кричит или убегает. "
        "Последствия всё равно есть — шум, свидетели, репутация."
    ),
    "critical_failure": (
        "Действие провалилось КАТАСТРОФИЧЕСКИ. Игрок получает урон или попадает в беду. "
        "Верни health_change с отрицательным delta. Репутация падает у всех свидетелей."
    ),
}

# ── Классификатор действий ────────────────────────────────

ACTION_KEYWORDS: dict[str, list[str]] = {
    "combat": [
        "бью", "бить", "ударяю", "ударить", "удар", "пинаю", "пнуть", "пинок",
        "атакую", "атаковать", "нападаю", "напасть", "дерусь", "дать в",
        "врезать", "врезаю", "замахиваюсь", "рублю", "колю", "режу",
        "кулаком", "мечом", "кинжалом", "дубиной", "зарезать", "зарезал",
        "убить", "убиваю", "нападаю", "избить", "избиваю",
    ],
    "intimidation": [
        "угрожаю", "угрожать", "угроза", "заставляю", "заставить",
        "принуждаю", "принудить", "шантажирую", "шантаж",
        "запугиваю", "запугать", "пригрозить", "пригрожу",
        "под угрозой", "ножом", "оружием заставил",
    ],
    "stealth": [
        "краду", "украсть", "кража", "стащить", "стащил", "ворую",
        "незаметно", "тихо", "скрытно", "прячусь", "прокрасться",
        "карманник", "обыскиваю", "обшариваю", "лезу в карман",
        "ограбить", "ограбляю",
    ],
    "persuasion": [
        "убеждаю", "убедить", "уговариваю", "уговорить",
        "торгуюсь", "прошу", "льщу", "соблазняю", "соблазнить",
        "договориться", "предлагаю сделку", "подкупаю",
    ],
    "athletics": [
        "прыгаю", "прыгнуть", "карабкаюсь", "лезу", "толкаю",
        "тащу", "ломаю", "сломать", "бегу", "бежать", "перелезть",
        "взобраться", "поднять", "бросить", "швырнуть",
    ],
}

SKILL_FOR_TYPE: dict[str, str] = {
    "combat": "меч",
    "intimidation": "харизма",
    "stealth": "скрытность",
    "persuasion": "харизма",
    "athletics": "сила",
    "general": "",  # выбирается динамически
}


@dataclass
class DiceRoll:
    raw: int           # 1–20, результат d20
    modifier: int      # сумма всех модификаторов
    total: int         # raw + modifier
    outcome: str       # critical_success | success | failure | critical_failure
    skill_used: str    # название навыка
    action_type: str   # тип действия


class ActionClassifier:
    def classify(self, command: str) -> str:
        """Определить тип действия по тексту команды."""
        cmd_lower = command.lower()
        for action_type, keywords in ACTION_KEYWORDS.items():
            if any(kw in cmd_lower for kw in keywords):
                return action_type
        return "general"

    def get_skill_for_type(self, action_type: str, skills: dict[str, int]) -> tuple[str, int]:
        """Вернуть (название навыка, значение) для типа действия."""
        skill_name = SKILL_FOR_TYPE.get(action_type, "")
        if skill_name and skill_name in skills:
            return skill_name, skills[skill_name]
        if action_type == "general" and skills:
            # Берём навык с максимальным значением
            best = max(skills.items(), key=lambda x: x[1])
            return best[0], best[1]
        return skill_name or "общий", 1


class DiceRoller:
    def roll(
        self,
        action_type: str,
        skill_name: str,
        skill_value: int,
        equipped_bonus: dict | None = None,
        reputation: int = 0,
    ) -> DiceRoll:
        """Бросить d20 и вернуть DiceRoll."""
        raw = random.randint(1, 20)
        modifier = self._calc_modifier(skill_value, action_type, equipped_bonus or {}, reputation)
        total = raw + modifier
        outcome = self._determine_outcome(total)
        return DiceRoll(
            raw=raw,
            modifier=modifier,
            total=total,
            outcome=outcome,
            skill_used=skill_name,
            action_type=action_type,
        )

    @staticmethod
    def _calc_modifier(
        skill_value: int,
        action_type: str,
        equipped_bonus: dict,
        reputation: int,
    ) -> int:
        modifier = skill_value // 5

        # Бонус от экипировки
        if action_type == "combat":
            modifier += equipped_bonus.get("меч", 0)
        # Бонус брони учитывается при контратаке — не здесь

        # Репутационный бонус
        if reputation > 50:
            modifier += 4
        elif reputation > 20:
            modifier += 2
        elif reputation < -50:
            modifier -= 4
        elif reputation < -20:
            modifier -= 2

        return modifier

    @staticmethod
    def _determine_outcome(total: int) -> str:
        if total >= 20:
            return "critical_success"
        elif total >= 12:
            return "success"
        elif total >= 6:
            return "failure"
        else:
            return "critical_failure"


class ActionResolver:
    """Оркестрирует классификацию, бросок и формирование промпта для GM."""

    def __init__(self) -> None:
        self.classifier = ActionClassifier()
        self.roller = DiceRoller()

    def resolve(
        self,
        command: str,
        player: "Player",
        npc_targets: list["NPC"],
        witnesses: list["NPC"],
    ) -> tuple[DiceRoll, str]:
        """
        Классифицировать действие, бросить кубик, сформировать расширенный промпт.
        Возвращает (DiceRoll, промпт для GM).
        """
        action_type = self.classifier.classify(command)
        skill_name, skill_value = self.classifier.get_skill_for_type(action_type, player.skills)

        # Репутация у первой цели (если есть)
        reputation = 0
        if npc_targets:
            reputation = player.reputation.get(npc_targets[0].id, 0)

        equipped_bonus = player.get_equipped_bonus() if hasattr(player, "get_equipped_bonus") else {}

        roll = self.roller.roll(
            action_type=action_type,
            skill_name=skill_name,
            skill_value=skill_value,
            equipped_bonus=equipped_bonus,
            reputation=reputation,
        )

        prompt = self._build_dice_prompt(command, roll, npc_targets, witnesses)
        return roll, prompt

    def _build_dice_prompt(
        self,
        command: str,
        roll: DiceRoll,
        npc_targets: list["NPC"],
        witnesses: list["NPC"],
    ) -> str:
        outcome_ru = OUTCOME_RU.get(roll.outcome, roll.outcome)
        instruction = OUTCOME_INSTRUCTIONS.get(roll.outcome, "")

        targets_str = ", ".join(n.name for n in npc_targets) or "нет"
        witnesses_str = ", ".join(n.name for n in witnesses) or "нет"

        return (
            f"=== РЕЗУЛЬТАТ БРОСКА ===\n"
            f"Действие: {roll.action_type} | Навык: {roll.skill_used} ({roll.skill_used})\n"
            f"Бросок: d20={roll.raw} + модификатор={roll.modifier} = {roll.total}\n"
            f"Исход: {outcome_ru}\n\n"
            f"{instruction}\n\n"
            f"Цели: {targets_str}\n"
            f"Свидетели: {witnesses_str}\n"
            f"========================\n\n"
            f"Команда игрока: {command}"
        )

    @staticmethod
    def format_roll_line(roll: DiceRoll) -> str:
        """Форматировать строку броска для вывода игроку."""
        outcome_ru = OUTCOME_RU.get(roll.outcome, roll.outcome)
        return f"[🎲 d20: {roll.raw} + {roll.modifier} ({roll.skill_used}) = {roll.total} — {outcome_ru}]"
