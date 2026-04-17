"""Игровой цикл — центральный координатор Echo-Sim."""
from __future__ import annotations
import random
from typing import Literal

from echo_sim.core.config import load_config
from echo_sim.core.world import World
from echo_sim.core.player import Player, Quest
from echo_sim.core.npc import NPC
from echo_sim.core.gm import GameMaster, GameEvent
from echo_sim.core.ambient import roll_ambient
from echo_sim.core.dice import ActionResolver

BUILTIN_COMMANDS = {"look", "inventory", "status", "go", "talk", "restart", "quit"}
TICK_MINUTES = 60

# Русские алиасы команд → английский глагол
RU_COMMANDS: dict[str, str] = {
    # осмотреться
    "осмотреться": "look", "осмотрись": "look", "смотреть": "look",
    "оглядеться": "look", "оглядись": "look", "где я": "look",
    # инвентарь
    "инвентарь": "inventory", "вещи": "inventory", "сумка": "inventory",
    "предметы": "inventory", "карманы": "inventory",
    # статус
    "статус": "status", "персонаж": "status", "характеристики": "status",
    "здоровье": "status", "навыки": "status",
    # идти
    "идти": "go", "иди": "go", "пойти": "go", "идём": "go",
    "перейти": "go", "двигаться": "go",
    # говорить
    "говорить": "talk", "поговорить": "talk", "поговори": "talk",
    "разговор": "talk", "спросить": "talk",
    # магазин
    "магазин": "shop", "торговля": "shop", "купить": "buy",
    "продать": "sell", "товары": "shop",
    # атака
    "атаковать": "attack", "атакую": "attack", "бить": "attack",
    "ударить": "attack", "напасть": "attack", "убить": "attack",
    # сохранение
    "сохранить": "save", "сохрани": "save",
    "загрузить": "load", "загрузи": "load",
    # прочее
    "рестарт": "restart", "заново": "restart", "выход": "quit", "выйти": "quit",
    "помощь": "help", "команды": "help",
}


class Engine:
    def __init__(self, config_path: str = "echo_sim/config/world.json") -> None:
        self.config_path = config_path
        self.config = load_config(config_path)
        self._init_from_config()

    def _init_from_config(self) -> None:
        self.world = World(self.config)
        self.player = Player(self.config)
        self.npcs: dict[str, NPC] = {}
        for npc_data in self.config.get("npcs", []):
            npc = NPC(npc_data)
            self.npcs[npc.id] = npc
        self.gm = GameMaster(self.config)
        self.state: Literal["active", "game_over"] = "active"
        self._pending_rumors: list[dict] = []
        self._pending_ambient: list[str] = []
        self._last_ambient_tick: int = -999
        self._npc_id_counter: int = 1000
        self._action_resolver = ActionResolver()

    def process_command(self, command: str) -> str:
        """Обработать команду игрока. Возвращает строку ответа."""
        command = command.strip()
        if not command:
            return ""

        if self.state == "game_over":
            cmd_lower = command.lower()
            if cmd_lower in ("restart", "рестарт", "заново"):
                self.reset()
                return self._start_message()
            elif cmd_lower in ("quit", "выход", "выйти"):
                raise SystemExit(0)
            else:
                return "[Игра окончена. Введите 'рестарт' или 'restart' для новой игры]"

        parts = command.split(maxsplit=1)
        verb_raw = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # Перевод русских команд
        verb = RU_COMMANDS.get(verb_raw, verb_raw)

        if verb == "look":
            return self._cmd_look()
        elif verb == "inventory":
            return self._cmd_inventory()
        elif verb == "status":
            return self._cmd_status()
        elif verb == "go":
            return self._cmd_go(arg)
        elif verb == "talk":
            return self._cmd_talk(arg)
        elif verb == "shop":
            return self._cmd_shop(arg)
        elif verb == "buy":
            return self._cmd_buy(arg)
        elif verb == "sell":
            return self._cmd_sell(arg)
        elif verb == "attack":
            return self._cmd_attack(arg or command)
        elif verb == "save":
            path = arg or "savegame.json"
            self.save_game(path)
            return f"Игра сохранена."
        elif verb == "load":
            path = arg or "savegame.json"
            if self.load_game(path):
                return "Игра загружена.\n" + self._cmd_look()
            return "Файл сохранения не найден."
        elif verb == "help":
            return self._cmd_help()
        elif verb in ("журнал", "дневник", "journal"):
            return self._cmd_journal()
        elif verb in ("карта", "map", "места"):
            return self._cmd_map()
        elif verb in ("quit", "выход", "выйти"):
            raise SystemExit(0)
        elif verb in ("restart", "рестарт", "заново"):
            self.reset()
            return self._start_message()
        else:
            return self._free_action(command)

    def _cmd_look(self) -> str:
        """Осмотреться — GM описывает локацию живо, не шаблонно."""
        world_ctx = self._build_world_ctx()
        response = self.gm.generate(world_ctx, "Я осматриваюсь вокруг.")
        self.apply_events(response.events)
        return response.narrative

    def _cmd_inventory(self) -> str:
        if not self.player.inventory:
            return "Инвентарь пуст."
        return "Инвентарь: " + ", ".join(self.player.inventory)

    def _cmd_status(self) -> str:
        p = self.player
        skills_str = ", ".join(f"{k}: {v}" for k, v in p.skills.items())
        quests_str = ""
        if p.active_quests:
            quests_str = "\nКвесты: " + ", ".join(
                f"{q.title} [{q.status}]" for q in p.active_quests
            )
        return (
            f"Персонаж: {p.name}\n"
            f"Здоровье: {p.health}/{p.max_health}\n"
            f"Навыки: {skills_str}"
            f"{quests_str}"
        )

    def _cmd_go(self, location_id: str) -> str:
        if not location_id:
            loc = self.world.locations.get(self.world.current_location_id)
            if loc and loc.adjacent_location_ids:
                adj = ", ".join(
                    f"{lid} ({self.world.locations[lid].name})"
                    for lid in loc.adjacent_location_ids
                    if lid in self.world.locations
                )
                return f"Куда идти? Выходы: {adj}"
            return "Некуда идти."
        if not self.world.move_player(location_id):
            return f"Локация '{location_id}' не существует."
        self.world_tick()
        # Отмечаем посещение на ментальной карте
        self.player.mark_visited(location_id, self.world.game_time)
        # GM описывает прибытие
        world_ctx = self._build_world_ctx()
        response = self.gm.generate(world_ctx, "Я прихожу в новое место.")
        self.apply_events(response.events)
        # Записываем в журнал
        if response.narrative:
            self.player.add_journal_entry(
                f"Пришёл в {self.world.locations.get(location_id, type('', (), {'name': location_id})()).name}: {response.narrative[:100]}",
                location_id, self.world.game_time
            )
        return response.narrative

    def _cmd_talk(self, npc_id: str) -> str:
        if not npc_id:
            return "С кем говорить? Укажи имя или id NPC."
        npc = self.npcs.get(npc_id)
        if not npc:
            return f"NPC '{npc_id}' не найден."
        if npc.status == "dead":
            return f"{npc.name} мёртв."
        if npc.location_id != self.world.current_location_id:
            return f"{npc.name} сейчас не здесь."

        world_ctx = self._build_world_ctx()
        response = self.gm.generate(world_ctx, f"Я говорю с {npc.name}")
        npc.add_memory(f"Игрок заговорил со мной")
        npc.add_player_action(f"Игрок начал разговор")
        narrative = self.apply_events(response.events)
        self.world_tick()
        return response.narrative + (f"\n{narrative}" if narrative else "")

    def _get_shop_for_location(self) -> tuple:
        """Найти магазин в текущей локации (по NPC-торговцу)."""
        shops = self.config.get("shop", {})
        for npc_id, shop_data in shops.items():
            npc = self.npcs.get(npc_id)
            if npc and npc.status == "alive" and npc.location_id == self.world.current_location_id:
                return npc_id, shop_data.get("items", [])
        return None, None

    def _parse_gold(self) -> int:
        for item in self.player.inventory:
            if item.startswith("кошель с монетами"):
                try:
                    return int(item.split("(")[1].rstrip(")"))
                except (IndexError, ValueError):
                    return 0
        return 0

    def _set_gold(self, amount: int) -> None:
        self.player.inventory = [
            i for i in self.player.inventory
            if not i.startswith("кошель с монетами")
        ]
        if amount > 0:
            self.player.inventory.append(f"кошель с монетами ({amount})")

    def _cmd_shop(self, arg: str) -> str:
        npc_id, items = self._get_shop_for_location()
        if not items:
            return "Здесь нет торговца."
        shop = self.config["shop"][npc_id]
        lines = [f"[{shop['name']}] — твоё золото: {self._parse_gold()}"]
        for item in items:
            req = ""
            if "skill_req" in item:
                for sk, val in item["skill_req"].items():
                    req = f" [требует {sk}: {val}]"
            lines.append(f"  {item['id']:20s} {item['name']:25s} {item['price']} зол.{req}")
        lines.append("Купить: buy <id>  |  Продать: sell <предмет>")
        return "\n".join(lines)

    def _cmd_buy(self, item_id: str) -> str:
        if not item_id:
            return "Что купить? Укажи id товара (смотри: магазин)."
        npc_id, items = self._get_shop_for_location()
        if not items:
            return "Здесь нет торговца."
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return f"Товар '{item_id}' не найден в этом магазине."
        for sk, val in item.get("skill_req", {}).items():
            if self.player.skills.get(sk, 0) < val:
                return f"Недостаточно навыка '{sk}' (нужно {val}, у тебя {self.player.skills.get(sk, 0)})."
        gold = self._parse_gold()
        if gold < item["price"]:
            return f"Недостаточно золота. Нужно {item['price']}, у тебя {gold}."
        self._set_gold(gold - item["price"])
        effect = item.get("effect", {})
        if "health" in effect:
            heal = min(effect["health"], self.player.max_health - self.player.health)
            self.player.apply_health_change(heal)
        if "skill_boost" in effect:
            self.player.apply_skill_growth(effect["skill_boost"], effect.get("delta", 1))
        if not effect:
            self.player.add_inventory_item(item["name"])
        # GM описывает сделку
        npc = self.npcs.get(npc_id)
        npc_name = npc.name if npc else "торговец"
        world_ctx = self._build_world_ctx()
        response = self.gm.generate(
            world_ctx,
            f"Я покупаю у {npc_name} '{item['name']}' за {item['price']} монет. Осталось золота: {self._parse_gold()}."
        )
        if npc:
            npc.add_memory(f"Продал игроку {item['name']} за {item['price']} монет")
        return response.narrative

    def _cmd_sell(self, item_name: str) -> str:
        if not item_name:
            return "Что продать? Укажи название предмета из инвентаря."
        npc_id, items = self._get_shop_for_location()
        if not items:
            return "Здесь нет торговца."
        if not self.player.remove_inventory_item(item_name):
            return f"'{item_name}' нет в инвентаре."
        catalog_item = next((i for i in items if i["name"] == item_name), None)
        sell_price = max(1, (catalog_item["price"] // 2) if catalog_item else 5)
        self._set_gold(self._parse_gold() + sell_price)
        npc = self.npcs.get(npc_id)
        npc_name = npc.name if npc else "торговец"
        world_ctx = self._build_world_ctx()
        response = self.gm.generate(
            world_ctx,
            f"Я продаю {npc_name} '{item_name}' за {sell_price} монет. Итого золота: {self._parse_gold()}."
        )
        if npc:
            npc.add_memory(f"Купил у игрока {item_name} за {sell_price} монет")
        return response.narrative

    def _cmd_attack(self, target: str) -> str:
        """Бой: механика через DiceSystem, нарратив через GM."""
        target_lower = target.lower()
        npc = None
        for n in self.npcs.values():
            if (n.location_id == self.world.current_location_id
                    and n.status == "alive"
                    and (n.id in target_lower or n.name.lower() in target_lower)):
                npc = n
                break

        if not npc:
            return self._free_action(target)

        # Бросок через DiceSystem
        loc_id = self.world.current_location_id
        witnesses = [n for n in self.npcs.values()
                     if n.status == "alive" and n.location_id == loc_id and n.id != npc.id]
        roll, dice_prompt = self._action_resolver.resolve(
            f"атакую {npc.name}", self.player, [npc], witnesses
        )
        roll_line = self._action_resolver.format_roll_line(roll)

        from echo_sim.core.dice import OUTCOME_RU
        hit = roll.outcome in ("critical_success", "success")

        if hit:
            base_damage = 5 if roll.outcome == "success" else 15
            damage = random.randint(base_damage, base_damage + 10) + self.player.skills.get("меч", 1) // 10
            counter_damage = random.randint(3, 12) if random.random() > 0.4 and roll.outcome == "success" else 0
            self.player.apply_health_change(-counter_damage)
            if random.random() < 0.3:
                self.player.apply_skill_growth("меч", 1)
            if self.player.health <= 0:
                self.state = "game_over"
            npc.add_memory(f"Игрок атаковал меня, нанёс {damage} урона", weight=2, about_player=True)
            gm_prompt = (
                f"{dice_prompt}\n\n"
                f"Я атакую {npc.name} и попадаю — наношу {damage} урона. "
                f"{'Он контратакует, я получаю ' + str(counter_damage) + ' урона.' if counter_damage else 'Он не успевает ответить.'} "
                f"Моё HP: {self.player.health}/{self.player.max_health}."
                + (" Я погибаю." if self.player.health <= 0 else "")
            )
        else:
            counter_damage = random.randint(5, 20) if roll.outcome == "critical_failure" else random.randint(3, 12)
            self.player.apply_health_change(-counter_damage)
            if self.player.health <= 0:
                self.state = "game_over"
            npc.add_memory(f"Игрок промахнулся, я ударил в ответ", weight=1, about_player=True)
            gm_prompt = (
                f"{dice_prompt}\n\n"
                f"Я атакую {npc.name} но промахиваюсь. "
                f"Он бьёт меня в ответ — {counter_damage} урона. "
                f"Моё HP: {self.player.health}/{self.player.max_health}."
                + (" Я погибаю." if self.player.health <= 0 else "")
            )

        world_ctx = self._build_world_ctx()
        response = self.gm.generate(world_ctx, gm_prompt)
        self.apply_events(response.events)
        self._record_witnesses(f"атакую {npc.name}", response.narrative, response.events)
        self.world_tick()
        return f"{roll_line}\n{response.narrative}"

    def _cmd_help(self) -> str:
        return (
            "Команды (русские и английские):\n"
            "  осмотреться / look          — описание локации\n"
            "  идти <куда> / go <id>       — перейти в локацию\n"
            "  говорить <кто> / talk <id>  — поговорить с NPC\n"
            "  атаковать <кто> / attack    — напасть на NPC\n"
            "  инвентарь / inventory       — список вещей\n"
            "  статус / status             — состояние персонажа\n"
            "  журнал / journal            — дневник событий\n"
            "  карта / map                 — запомненные места\n"
            "  магазин / shop              — список товаров\n"
            "  купить <id> / buy <id>      — купить товар\n"
            "  продать <предмет> / sell    — продать предмет\n"
            "  сохранить / save            — сохранить игру\n"
            "  загрузить / load            — загрузить игру\n"
            "  рестарт / restart           — начать заново\n\n"
            "Или просто пиши что делаешь — GM разберётся."
        )

    def _cmd_journal(self) -> str:
        if not self.player.journal:
            return "Дневник пуст — ты ещё ничего не записал."
        lines = ["Дневник:"]
        for entry in self.player.journal[-15:]:
            loc = self.world.locations.get(entry.location_id)
            loc_name = loc.name if loc else entry.location_id
            mark = "★ " if entry.important else "  "
            lines.append(f"{mark}[{loc_name}] {entry.text[:100]}")
        return "\n".join(lines)

    def _cmd_map(self) -> str:
        notes = [n for n in self.player.map_notes if n.label != "был здесь"]
        visited = list({n.location_id for n in self.player.map_notes if n.visited})
        lines = []
        if visited:
            names = [self.world.locations.get(lid, type('', (), {'name': lid})()).name for lid in visited]
            lines.append("Посещённые места: " + ", ".join(names))
        if notes:
            lines.append("\nЗапомнившиеся места:")
            for note in notes[-15:]:
                loc = self.world.locations.get(note.location_id)
                loc_name = loc.name if loc else note.location_id
                lines.append(f"  [{loc_name}] {note.label}")
        acq = self.player.get_acquaintance_summary()
        if acq:
            lines.append(f"\nЗнакомые: {acq}")
        return "\n".join(lines) if lines else "Ты ещё нигде не был."

    def _free_action(self, command: str) -> str:
        # Детектируем атаку на NPC в свободной команде
        npc_target = self._detect_npc_in_command(command)
        if npc_target and self._is_attack_command(command):
            return self._cmd_attack(npc_target.id)

        # Определяем нужен ли кубик — только для рискованных действий
        action_type = self._action_resolver.classifier.classify(command)
        needs_dice = action_type in ("combat", "intimidation", "stealth", "persuasion", "athletics")

        # Собираем цели и свидетелей
        loc_id = self.world.current_location_id
        all_loc_npcs = [n for n in self.npcs.values() if n.status == "alive" and n.location_id == loc_id]
        npc_targets = [npc_target] if npc_target else []
        witnesses = [n for n in all_loc_npcs if n not in npc_targets]

        world_ctx = self._build_world_ctx()

        if needs_dice:
            # Бросок кубика для рискованных действий
            roll, dice_prompt = self._action_resolver.resolve(command, self.player, npc_targets, witnesses)
            roll_line = self._action_resolver.format_roll_line(roll)
            response = self.gm.generate(world_ctx, dice_prompt)
            prefix = f"{roll_line}\n"
        else:
            # Обычное действие — без кубика, GM сам решает
            response = self.gm.generate(world_ctx, command)
            prefix = ""

        notifications = self.apply_events(response.events)

        # Записываем в журнал важные события
        has_spawn = any(e.type == "spawn_npc" for e in response.events)
        has_death = any(e.type == "npc_death" for e in response.events)
        is_important = has_spawn or has_death or needs_dice
        if response.narrative and is_important:
            self.player.add_journal_entry(
                f"{command[:50]}: {response.narrative[:120]}",
                self.world.current_location_id,
                self.world.game_time,
                important=has_death or has_spawn,
            )

        # Обновляем знакомства из spawn_npc событий
        for e in response.events:
            if e.type == "spawn_npc":
                p = e.payload
                name = p.get("name", "")
                if name:
                    self.player.meet_npc(
                        npc_id=p.get("id", name),
                        name=name,
                        description=f"{p.get('appearance', '')} {p.get('profession', '')}".strip(),
                        location_id=self.world.current_location_id,
                    )

        # Свидетели запоминают
        self._record_witnesses(command, response.narrative, response.events)

        self.world_tick()
        result = f"{prefix}{response.narrative}"
        if notifications:
            result += f"\n{notifications}"
        return result

    def _detect_npc_in_command(self, command: str) -> "NPC | None":
        """Найти NPC упомянутого в команде."""
        cmd_lower = command.lower()
        loc_id = self.world.current_location_id
        for npc in self.npcs.values():
            if npc.status != "alive" or npc.location_id != loc_id:
                continue
            # Проверяем id и части имени
            if npc.id in cmd_lower:
                return npc
            for part in npc.name.lower().split():
                if len(part) > 3 and part in cmd_lower:
                    return npc
        return None

    _ATTACK_WORDS = [
        "бью", "бить", "ударяю", "ударить", "удар", "пинаю", "пнуть", "пинок",
        "атакую", "атаковать", "нападаю", "напасть", "дерусь", "дать в",
        "врезать", "врезаю", "замахиваюсь", "рублю", "колю", "режу",
        "кулаком", "мечом", "кинжалом", "дубиной", "кулак",
    ]

    def _is_attack_command(self, command: str) -> bool:
        cmd_lower = command.lower()
        return any(w in cmd_lower for w in self._ATTACK_WORDS)

    def _record_witnesses(self, command: str, narrative: str, events: list) -> None:
        """Все NPC в текущей локации становятся свидетелями действия игрока."""
        loc_id = self.world.current_location_id
        witnesses = [
            npc for npc in self.npcs.values()
            if npc.status == "alive" and npc.location_id == loc_id
        ]
        if not witnesses:
            return

        # Определяем вес события по типам
        weight = 1
        event_types = {e.type for e in events}
        if "npc_death" in event_types:
            weight = 3  # убийство — критическое
        elif "health_change" in event_types:
            # Проверяем урон
            for e in events:
                if e.type == "health_change" and e.payload.get("delta", 0) < -10:
                    weight = 2  # серьёзное насилие
                    break
        elif any(k in command.lower() for k in ("украл", "украсть", "кража", "стащил", "вор")):
            weight = 2  # кража
        elif "inventory_change" in event_types:
            weight = 1

        # Краткое описание для памяти свидетелей
        short_narrative = narrative[:150].replace("\n", " ").strip()
        short_cmd = command[:80]
        memory_text = f"Игрок {short_cmd[:40]}: {short_narrative[:100]}"

        for npc in witnesses:
            npc.witnessed_player_action(memory_text, weight=weight)

        # Если вес >= 2 — событие расходится слухами в соседние локации
        if weight >= 2:
            rumor = f"Говорят, {self.player.name} {short_cmd[:60]} в {self.world.locations.get(loc_id, type('', (), {'name': loc_id})()).name}"
            self._pending_rumors.append({
                "description": rumor,
                "location_id": loc_id,
                "tick_delay": 1,
                "weight": weight,
            })

    def broadcast_event(self, description: str, loc_id: str, weight: int = 1) -> None:
        """Распространить значимое событие — свидетели запоминают, слухи расходятся."""
        witnesses = [
            npc for npc in self.npcs.values()
            if npc.status == "alive" and npc.location_id == loc_id
        ]
        for npc in witnesses:
            npc.witnessed_player_action(description, weight=weight)

        if weight >= 2:
            self._pending_rumors.append({
                "description": description,
                "location_id": loc_id,
                "tick_delay": 1,
                "weight": weight,
            })

    def _build_world_ctx(self) -> dict:
        scene = self.world.get_scene_context(self.npcs)
        p_state = self.player.get_state()
        rep_ctx = {}
        for npc in self.npcs.values():
            if npc.location_id == self.world.current_location_id:
                rep_ctx[npc.id] = self.player.reputation.get(npc.id, 0)
        return {
            **scene,
            "player": p_state,
            "active_quests": p_state["active_quests"],
            "reputation_context": rep_ctx,
            "player_journal": self.player.get_recent_journal(5),
            "player_map_notes": self.player.get_map_notes_for_location(self.world.current_location_id),
            "player_acquaintances": self.player.get_acquaintance_summary(),
        }

    def apply_events(self, events: list[GameEvent]) -> str:
        """Применить события от GM к состоянию. Возвращает строку с уведомлениями."""
        notifications = []
        for event in events:
            p = event.payload
            if event.type == "health_change":
                delta = p.get("delta", 0)
                self.player.apply_health_change(delta)
                if delta < 0:
                    notifications.append(f"[Здоровье: {self.player.health}/{self.player.max_health}]")
                if self.player.health <= 0:
                    self.state = "game_over"
                    notifications.append("[ИГРА ОКОНЧЕНА]")

            elif event.type == "skill_growth":
                skill = p.get("skill", "")
                delta = p.get("delta", 1)
                if skill:
                    self.player.apply_skill_growth(skill, delta)
                    notifications.append(f"[Навык '{skill}' вырос до {self.player.skills.get(skill, 0)}]")

            elif event.type == "reputation_change":
                target = p.get("target_id", "")
                delta = p.get("delta", 0)
                if target:
                    self.player.apply_reputation_change(target, delta)

            elif event.type == "quest_update":
                quest_id = p.get("quest_id", "")
                status = p.get("status", "")
                if quest_id and status:
                    self.player.update_quest_status(quest_id, status)
                    notifications.append(f"[Квест обновлён: {quest_id} → {status}]")

            elif event.type == "world_event":
                desc = p.get("description", "")
                loc_id = p.get("location_id", self.world.current_location_id)
                if desc:
                    self.world.new_event(desc, loc_id)
                    self._pending_rumors.append({
                        "description": desc,
                        "location_id": loc_id,
                        "tick_delay": 1,
                    })

            elif event.type == "map_note":
                # GM заметил что-то запоминающееся — добавляем на ментальную карту
                label = p.get("label", "")
                loc_id = p.get("location_id", self.world.current_location_id)
                if label:
                    self.player.add_map_note(loc_id, label, self.world.game_time)
                    notifications.append(f"[Запомнено: {label}]")

            elif event.type == "npc_death":
                npc_id = p.get("npc_id", "")
                if npc_id in self.npcs:
                    dead_npc = self.npcs[npc_id]
                    dead_npc.status = "dead"
                    notifications.append(f"[{dead_npc.name} погиб]")
                    death_desc = f"{self.player.name} убил {dead_npc.name}"
                    self.world.new_event(death_desc, dead_npc.location_id, event_type="npc_death")
                    # Все свидетели запоминают убийство с максимальным весом
                    self.broadcast_event(death_desc, dead_npc.location_id, weight=3)
                    # Автоматически снижаем репутацию у всех свидетелей
                    loc_id = dead_npc.location_id
                    for witness in self.npcs.values():
                        if witness.status == "alive" and witness.location_id == loc_id:
                            self.player.apply_reputation_change(witness.id, -15)

            elif event.type == "inventory_change":
                for item in p.get("add", []):
                    if isinstance(item, str) and item.strip():
                        self.player.add_inventory_item(item)
                        notifications.append(f"[Получено: {item}]")
                        # Записываем в журнал
                        self.player.add_journal_entry(
                            f"Получил: {item}",
                            self.world.current_location_id,
                            self.world.game_time,
                        )
                        # Если предмет явно чужой — свидетели запоминают кражу
                        if any(k in item.lower() for k in ("меч", "кинжал", "доспех", "кошель")):
                            stolen_desc = f"{self.player.name} взял {item}"
                            self.broadcast_event(stolen_desc, self.world.current_location_id, weight=2)
                for item in p.get("remove", []):
                    if isinstance(item, str) and self.player.remove_inventory_item(item):
                        notifications.append(f"[Потеряно: {item}]")

            elif event.type == "spawn_npc":
                name = p.get("name", "").strip()
                # Не спавним если NPC с таким именем уже существует
                already_exists = any(
                    n.name.lower() == name.lower()
                    for n in self.npcs.values()
                    if n.status == "alive"
                ) if name else True
                if not already_exists:
                    spawned = self._spawn_dynamic_npc(p)
                    if spawned:
                        notifications.append(f"[Новый персонаж: {spawned.name}]")

        return "\n".join(notifications)

    def world_tick(self) -> None:
        """Тик мирового времени: обновить NPC, ambient, слухи."""
        self.world.game_time += TICK_MINUTES

        for npc in self.npcs.values():
            if npc.status == "alive":
                npc.update(self.world.game_time, self.gm, self.world)

        # Автономные взаимодействия NPC (раз в 3 тика)
        if self.world.game_time % (TICK_MINUTES * 3) == 0:
            self._run_npc_autonomy()

        # Фоновые события (ambient) — если игрок просто стоит
        self._try_ambient_event()

        # Распространить слухи — критические (weight>=3) идут дальше и с большим весом
        remaining = []
        for rumor in self._pending_rumors:
            if rumor["tick_delay"] <= 0:
                weight = rumor.get("weight", 1)
                adjacent_npcs = self.world.get_adjacent_npcs(rumor["location_id"], self.npcs)
                for npc in adjacent_npcs:
                    npc.heard_rumor(rumor["description"])
                # Критические слухи (убийство) расходятся ещё на один уровень через тик
                if weight >= 3:
                    for adj_npc in adjacent_npcs:
                        self._pending_rumors.append({
                            "description": rumor["description"],
                            "location_id": adj_npc.location_id,
                            "tick_delay": 2,
                            "weight": 1,  # дальше идёт как обычный слух
                        })
            else:
                rumor["tick_delay"] -= 1
                remaining.append(rumor)
        self._pending_rumors = remaining

    def _try_ambient_event(self) -> None:
        """Попробовать сгенерировать фоновое событие — GM придумывает сам."""
        trigger = roll_ambient(
            self.world.current_location_id,
            self.world.game_time,
            self._last_ambient_tick,
        )
        if not trigger:
            return

        self._last_ambient_tick = self.world.game_time
        world_ctx = self._build_world_ctx()

        try:
            response = self.gm.generate_ambient(world_ctx, trigger)
        except Exception:
            return

        if not response.narrative or len(response.narrative) < 5:
            return

        self._pending_ambient.append(response.narrative)
        self.apply_events(response.events)
        self.world.new_event(
            response.narrative[:150],
            self.world.current_location_id,
            event_type="ambient",
        )

    def _spawn_dynamic_npc(self, payload: dict) -> NPC | None:
        """Создать нового NPC из payload события spawn_npc."""
        name = payload.get("name", "").strip()
        if not name:
            return None

        npc_id = payload.get("id", "").strip()
        # Транслитерируем имя в id если не задан или занят
        if not npc_id or npc_id in self.npcs:
            self._npc_id_counter += 1
            npc_id = f"dynamic_{self._npc_id_counter}"

        loc_id = payload.get("location_id", self.world.current_location_id)
        goals = payload.get("goals", ["жить своей жизнью"])
        appearance = payload.get("appearance", "")
        profession = payload.get("profession", "")

        # Формируем начальную память — внешность + профессия + контекст знакомства
        memory = list(payload.get("memory", []))
        if appearance and f"Внешность: {appearance}" not in memory:
            memory.insert(0, f"Внешность: {appearance}")
        if profession and f"Профессия: {profession}" not in memory:
            memory.insert(1 if appearance else 0, f"Профессия: {profession}")

        # Добавляем в goals профессиональные цели если не заданы
        if not goals or goals == ["жить своей жизнью"]:
            if profession:
                goals = [f"заниматься своим делом ({profession})", "жить своей жизнью"]

        npc_data = {
            "id": npc_id,
            "name": name,
            "location_id": loc_id,
            "goals": goals,
            "memory": memory[-10:],
            "player_actions_memory": [f"Игрок познакомился со мной"],
            "status": "alive",
            "schedule": [],
        }
        npc = NPC(npc_data)
        self.npcs[npc_id] = npc

        # Фиксируем появление как мировое событие
        desc = f"{name}"
        if profession:
            desc += f" ({profession})"
        desc += " появился в мире"
        self.world.new_event(desc, loc_id, event_type="npc_action")

        return npc

    def _run_npc_autonomy(self) -> None:
        """Автономные действия NPC — GM решает что происходит между ними."""
        by_location: dict[str, list] = {}
        for npc in self.npcs.values():
            if npc.status == "alive":
                by_location.setdefault(npc.location_id, []).append(npc)

        for loc_id, npcs_here in by_location.items():
            if len(npcs_here) < 2:
                continue
            a, b = npcs_here[0], npcs_here[1]
            loc = self.world.locations.get(loc_id)
            if not loc:
                continue
            # Передаём GM полный контекст — он сам придумает что происходит
            ctx = {
                "location": loc.to_dict(),
                "game_time": self.world._format_time(),
                "npcs_present": [a.get_context(), b.get_context()],
                "recent_events": [e.to_dict() for e in loc.events[-3:]],
                "player": {"name": "", "health": 0, "max_health": 0, "skills": {}, "inventory": [], "active_quests": []},
                "active_quests": [],
                "reputation_context": {},
            }
            try:
                response = self.gm.generate(ctx, f"{a.name} и {b.name} находятся вместе. Что они делают?")
                if response.narrative and len(response.narrative) > 10:
                    self.world.new_event(response.narrative[:200], loc_id, event_type="npc_action")
                    a.add_memory(response.narrative[:100])
                    b.add_memory(response.narrative[:100])
                    self._pending_rumors.append({
                        "description": response.narrative[:80],
                        "location_id": loc_id,
                        "tick_delay": 1,
                    })
            except Exception:
                pass

    def get_full_state(self) -> dict:
        return {
            "world": self.world.get_state(),
            "player": self.player.get_state(),
            "npcs": {nid: npc.get_state() for nid, npc in self.npcs.items()},
            "game_state": self.state,
        }

    def save_game(self, path: str = "savegame.json") -> None:
        """Сохранить текущее состояние игры в JSON-файл."""
        import json
        state = self.get_full_state()
        state["session_context"] = self.gm.session_context
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_game(self, path: str = "savegame.json") -> bool:
        """Загрузить состояние из JSON-файла. Возвращает True при успехе."""
        import json, os
        if not os.path.exists(path):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            return False

        # Восстановить мир
        w = state.get("world", {})
        self.world.game_time = w.get("game_time", 0)
        self.world.current_location_id = w.get("current_location_id", self.world.current_location_id)
        for evt_data in w.get("event_log", []):
            from echo_sim.core.world import WorldEvent
            evt = WorldEvent(**evt_data)
            if not any(e.id == evt.id for e in self.world.event_log):
                self.world.event_log.append(evt)

        # Восстановить игрока
        p = state.get("player", {})
        self.player.health = p.get("health", self.player.health)
        self.player.skills = p.get("skills", self.player.skills)
        self.player.inventory = p.get("inventory", self.player.inventory)
        self.player.reputation = p.get("reputation", {})
        from echo_sim.core.player import Quest
        self.player.active_quests = [
            Quest(**q) for q in p.get("active_quests", [])
        ]

        # Восстановить NPC
        for nid, npc_data in state.get("npcs", {}).items():
            if nid in self.npcs:
                self.npcs[nid].location_id = npc_data.get("location_id", self.npcs[nid].location_id)
                self.npcs[nid].memory = npc_data.get("memory", [])
                self.npcs[nid].player_actions_memory = npc_data.get("player_actions_memory", [])
                self.npcs[nid].status = npc_data.get("status", "alive")

        # Восстановить контекст сессии GM
        self.gm.session_context = state.get("session_context", [])
        self.state = state.get("game_state", "active")
        return True

    def reset(self) -> None:
        """Сбросить игру к начальному состоянию."""
        self.config = load_config(self.config_path)
        self._init_from_config()

    def _start_message(self) -> str:
        """GM генерирует вступление — уникальное каждый раз."""
        world_ctx = self._build_world_ctx()
        p = self.player
        response = self.gm.generate(
            world_ctx,
            f"Начало игры. {p.name} только что появился здесь. Опиши момент прибытия — коротко, атмосферно."
        )
        return response.narrative
