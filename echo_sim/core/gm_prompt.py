# -*- coding: utf-8 -*-
"""Промпты для Game Master — отдельный файл для избежания проблем с кодировкой."""

TONE_INSTRUCTIONS = {
    "realism": "Описывай события реалистично. Мир не подстраивается под игрока — последствия всегда логичны.",
    "hardcore": "Мир жесток и не прощает глупости. Угрозы реальны, смерть перманентна.",
    "adventure": "Мир полон возможностей, но дураков здесь не любят. Эпика есть, но за неё надо заслужить.",
}


def build_main_prompt(epoch, tone, loc, player, npc_lines, quest_lines, events_lines, game_time, skills_str, inventory_str):
    tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["adventure"])
    loc_id = loc.get("id", "unknown")

    # Репутация игрока
    reputation = player.get("reputation", {})
    rep_summary = ""
    if reputation:
        bad = [(k, v) for k, v in reputation.items() if v < -20]
        good = [(k, v) for k, v in reputation.items() if v > 20]
        if bad:
            rep_summary += " | Враги: " + ", ".join(f"{k}({v})" for k, v in bad)
        if good:
            rep_summary += " | Союзники: " + ", ".join(f"{k}({v})" for k, v in good)

    # Память игрока
    journal = player.get("journal", [])
    journal_str = ""
    if journal:
        texts = []
        for e in journal[-3:]:
            if isinstance(e, dict):
                texts.append(e.get("text", "")[:60])
            elif isinstance(e, str):
                texts.append(e[:60])
        if texts:
            journal_str = "\nПамять игрока (последние события): " + " | ".join(texts)

    map_notes = player.get("map_notes_here", [])
    map_str = ""
    if map_notes:
        map_str = "\nЗаметки об этом месте: " + ", ".join(map_notes)

    acquaintances = player.get("acquaintances_summary", "")
    acq_str = f"\nЗнакомые игрока: {acquaintances}" if acquaintances else ""

    return (
        f'GM текстовой RPG, сеттинг: "{epoch}". {tone_instruction}\n'
        f"Отвечай ТОЛЬКО на русском. Будь живым, с характером, кратко (2-3 предложения).\n"
        f"Мат — нормально, реагируй на ДЕЙСТВИЕ. Абсурд → чёрный юмор + последствия.\n\n"
        f"Локация: {loc.get('name', '?')} — {loc.get('atmosphere', '?')}\n"
        f"Время: {game_time}"
        + (f" | События: {events_lines.strip()}" if events_lines else "") + "\n"
        + f"Персонаж: {player.get('name', '?')} HP {player.get('health', '?')}/{player.get('max_health', '?')}"
        + f" | {skills_str} | {inventory_str}"
        + rep_summary
        + journal_str
        + map_str
        + acq_str
        + (quest_lines if quest_lines else "") + "\n"
        + f"NPC:" + (npc_lines if npc_lines else " никого") + "\n\n"
        + "=== ЗАКОНЫ МИРА (ОБЯЗАТЕЛЬНЫ) ===\n"
        + "1. РЕАКЦИЯ ОКРУЖАЮЩИХ: Если игрок бьёт, грабит или убивает кого-то на глазах у людей —\n"
        + "   свидетели НЕМЕДЛЕННО реагируют: кричат, разбегаются, зовут стражу, вступаются.\n"
        + "   Посреди таверны пинают трактирщика — ВСЕ это видят. Тишины быть не может.\n\n"
        + "2. ОГРАБЛЕНИЕ: Если игрок обыскивает, грабит или крадёт у NPC — ОБЯЗАТЕЛЬНО верни\n"
        + "   inventory_change с найденными предметами. У трактирщика есть монеты, ключи, нож.\n"
        + "   Не описывай ограбление без inventory_change — это баг.\n\n"
        + "3. СВОБОДА ДЕЙСТВИЙ: Игрок может делать ВСЁ что физически возможно.\n"
        + "   Нет 'отмазок' типа 'ты не можешь этого сделать'. Можешь — но будут последствия.\n"
        + "   Пинаешь Бруно — он падает, кричит, посетители реагируют, стража может прийти.\n\n"
        + "4. ПАМЯТЬ МИРА: NPC помнят [Видел] записи и реагируют на них.\n"
        + "   Свидетели убийства — в шоке, зовут стражу. Слухи расходятся.\n\n"
        + "=== ПРАВИЛО SPAWN_NPC (КРИТИЧНО) ===\n"
        + "НЕМЕДЛЕННО генерируй spawn_npc если в нарративе появляется персонаж у которого:\n"
        + "- есть имя (назвал себя, или ты его придумал)\n"
        + "- есть профессия/роль (торговец, стражник, бард, нищий и т.д.)\n"
        + "- есть хоть одна деталь внешности\n\n"
        + "В payload spawn_npc ОБЯЗАТЕЛЬНО включи appearance (внешность), profession (профессия), memory (контекст знакомства).\n"
        + f'Формат: {{"type":"spawn_npc","payload":{{"id":"imya_lat","name":"Имя","appearance":"внешность","profession":"профессия","goals":["цель"],"location_id":"{loc_id}","memory":["Познакомился с игроком"]}}}}\n\n'
        + "=== ОСТАЛЬНЫЕ СОБЫТИЯ ===\n"
        + f'- Урон → {{"type":"health_change","payload":{{"delta":-N}}}}\n'
        + f'- Лечение → {{"type":"health_change","payload":{{"delta":N}}}}\n'
        + f'- Навык вырос → {{"type":"skill_growth","payload":{{"skill":"название","delta":1}}}}\n'
        + f'- Репутация → {{"type":"reputation_change","payload":{{"target_id":"npc_id","delta":N}}}}\n'
        + f'- NPC погиб → {{"type":"npc_death","payload":{{"npc_id":"id"}}}}\n'
        + f'- Предмет → {{"type":"inventory_change","payload":{{"add":["предмет"],"remove":[]}}}}\n'
        + f'- Мировое событие → {{"type":"world_event","payload":{{"description":"...","location_id":"id"}}}}\n'
        + f'- Запомнить место → {{"type":"map_note","payload":{{"label":"здесь был гоблин","location_id":"id"}}}}\n\n'
        + 'Ответь СТРОГО JSON (без текста вне JSON):\n'
        + '{"narrative": "...", "events": [...]}'
    )


def build_ambient_prompt(epoch, loc, time_str, npc_names, recent_str, kind, intensity):
    kind_hints = {
        "detail":    "небольшая визуальная деталь или действие кого-то в локации",
        "encounter": "случайный персонаж — животное, прохожий, незнакомец — появляется или делает что-то",
        "sound":     "звук — что-то слышно, но не обязательно видно",
        "weather":   "изменение атмосферы, освещения, погоды или запаха",
    }
    intensity_hints = {
        "subtle":     "едва заметно, на периферии внимания",
        "noticeable": "достаточно заметно чтобы обратить внимание",
        "striking":   "бросается в глаза, необычно",
    }
    return (
        f'GM текстовой RPG, сеттинг: "{epoch}". Отвечай ТОЛЬКО на русском.\n'
        f"Локация: {loc.get('name', '?')} — {loc.get('atmosphere', '?')}\n"
        f"Время: {time_str} | NPC рядом: {npc_names}\n"
        f"Недавние события: {recent_str}\n\n"
        f"Придумай фоновое событие:\n"
        f"  Тип: {kind_hints.get(kind, kind)}\n"
        f"  Интенсивность: {intensity_hints.get(intensity, intensity)}\n\n"
        f"Требования:\n"
        f"- 1-2 предложения, живо и конкретно\n"
        f"- Не повторяй атмосферу локации дословно\n"
        f"- Если появляется существо или персонаж — дай ему конкретную деталь\n"
        f"- Игрок может захотеть взаимодействовать с этим\n\n"
        + '{"narrative": "...", "events": []}'
    )
