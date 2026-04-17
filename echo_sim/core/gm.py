# -*- coding: utf-8 -*-
"""Game Master -- interaction with ollama LLM."""
from __future__ import annotations
import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Callable, Optional

from echo_sim.core.gm_prompt import build_main_prompt, build_ambient_prompt

OLLAMA_URL = "http://localhost:11434/api/generate"
TIMEOUT_SECONDS = 120


@dataclass
class GameEvent:
    type: str
    payload: dict = field(default_factory=dict)


@dataclass
class GMResponse:
    narrative: str
    events: list[GameEvent] = field(default_factory=list)


class GameMaster:
    def __init__(self, config: dict) -> None:
        self.model: str = config.get("llm_model", "llama3")
        self.tone: str = config.get("narrative_tone", "adventure")
        self.context_window: int = config.get("context_size", 20)
        self.epoch: str = config.get("epoch", "medieval")
        self.session_context: list[dict] = []
        self.stream_callback: Optional[Callable[[str], None]] = None

    def generate(self, world_ctx: dict, command: str) -> GMResponse:
        system_prompt = self._build_system_prompt(world_ctx)
        messages = self._build_messages(command)
        raw = self._call_ollama(system_prompt, messages)
        response = self._parse_response(raw)
        self.session_context.append({"role": "user", "content": command})
        self.session_context.append({"role": "assistant", "content": response.narrative})
        if len(self.session_context) > self.context_window * 2:
            self.session_context = self.session_context[-(self.context_window * 2):]
        return response

    def _build_system_prompt(self, world_ctx: dict) -> str:
        loc = world_ctx.get("location", {})
        player = world_ctx.get("player", {})
        npcs = world_ctx.get("npcs_present", [])
        quests = world_ctx.get("active_quests", [])
        recent_events = world_ctx.get("recent_events", [])

        npc_lines = ""
        for npc in npcs:
            rep = world_ctx.get("reputation_context", {}).get(npc.get("id", ""), 0)
            npc_lines += (
                f"\n  {npc.get('name', '?')} (rep: {rep}): "
                f"goals={npc.get('goals', [])}, "
                f"memory={npc.get('memory', [])[-5:]}, "
                f"appearance={npc.get('appearance', '')}"
            )

        quest_lines = ""
        for q in quests:
            quest_lines += f"\n  [{q.get('status', '?')}] {q.get('title', '?')}: {q.get('description', '')}"

        events_lines = ""
        for e in recent_events:
            events_lines += f"\n  - {e.get('description', '')}"

        skills_str = ", ".join(f"{k}: {v}" for k, v in player.get("skills", {}).items())
        inventory_str = ", ".join(player.get("inventory", []))
        game_time = world_ctx.get("game_time", "00:00")

        # Добавляем память игрока в контекст для промпта
        player["journal"] = world_ctx.get("player_journal", [])
        player["map_notes_here"] = world_ctx.get("player_map_notes", [])
        player["acquaintances_summary"] = world_ctx.get("player_acquaintances", "")

        return build_main_prompt(
            self.epoch, self.tone, loc, player,
            npc_lines, quest_lines, events_lines,
            game_time, skills_str, inventory_str,
        )
    def _build_messages(self, command: str) -> list[dict]:
        recent = self.session_context[-(self.context_window * 2):]
        messages = list(recent)
        messages.append({"role": "user", "content": command})
        return messages

    def _call_ollama(self, system_prompt: str, messages: list[dict]) -> str:
        full_prompt = system_prompt + "\n\n"
        for msg in messages:
            role = "Igrok" if msg["role"] == "user" else "GM"
            full_prompt += f"{role}: {msg['content']}\n"

        payload = json.dumps({
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
        }).encode("utf-8")

        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            result = []
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        token = chunk.get("response", "")
                        if token:
                            result.append(token)
                            if self.stream_callback:
                                self.stream_callback(token)
                            else:
                                print(token, end="", flush=True)
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
            if not self.stream_callback:
                print()
            return "".join(result)
        except urllib.error.URLError:
            return "GM nedostupen: ollama ne zapushchen"
        except TimeoutError:
            return "GM nedostupen: prevysheno vremya ozhidaniya"
        except Exception as e:
            return f"GM nedostupen: {e}"

    def _parse_response(self, raw: str) -> GMResponse:
        # Убираем markdown и лишние пробелы
        cleaned = re.sub(r'```(?:json)?\s*', '', raw).strip()
        cleaned = re.sub(r'```\s*$', '', cleaned).strip()

        data = None

        # Собираем все валидные JSON-объекты с "narrative" — берём последний
        candidates = []
        for m in re.finditer(r'\{', cleaned):
            try:
                candidate = json.loads(cleaned[m.start():])
                if "narrative" in candidate:
                    candidates.append(candidate)
            except json.JSONDecodeError:
                pass

        if candidates:
            # Берём последний — модели иногда исправляют себя
            data = candidates[-1]

        if data is not None:
            narrative = data.get("narrative", "").strip()
            events_raw = data.get("events", [])
        else:
            # Fallback: вытащить narrative regex-ом — даже из незакрытого JSON
            nm = re.search(r'"narrative"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
            if nm:
                narrative = nm.group(1).replace('\\"', '"').replace('\\n', '\n').strip()
            else:
                # Последний шанс — убрать всё что похоже на JSON-обёртку
                narrative = re.sub(r'^\s*\{?\s*"narrative"\s*:\s*"?', '', cleaned)
                narrative = re.sub(r'"?\s*,?\s*"events"\s*:.*$', '', narrative, flags=re.DOTALL)
                narrative = narrative.strip().strip('"').strip()
            events_raw = []

        # Убираем экранирование если осталось
        narrative = narrative.replace('\\n', '\n').replace('\\"', '"')

        events = []
        for e in events_raw:
            if isinstance(e, dict) and "type" in e:
                events.append(GameEvent(type=e["type"], payload=e.get("payload", {})))

        return GMResponse(narrative=narrative or raw.strip(), events=events)

    def generate_ambient(self, world_ctx: dict, trigger) -> GMResponse:
        loc = world_ctx.get("location", {})
        time_str = world_ctx.get("game_time", "00:00")
        npcs = world_ctx.get("npcs_present", [])
        recent = world_ctx.get("recent_events", [])

        npc_names = ", ".join(n.get("name", "") for n in npcs) or "nikogo"
        recent_str = "; ".join(e.get("description", "") for e in recent[-2:]) or "nichego"

        kind = getattr(trigger, "kind", "detail")
        intensity = getattr(trigger, "intensity", "subtle")

        prompt = build_ambient_prompt(self.epoch, loc, time_str, npc_names, recent_str, kind, intensity)
        raw = self._call_ollama(prompt, [])
        return self._parse_response(raw)
