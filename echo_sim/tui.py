"""TUI для Echo-Sim на базе Textual — 3 панели: нарратив, статус, ввод."""
from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.widgets import RichLog, Static, Input, Footer
from textual.containers import Horizontal, Vertical
from textual import work

if TYPE_CHECKING:
    from echo_sim.core.engine import Engine

EPOCH_THEMES = {
    "post-apocalyptic": "post_apocalyptic",
    "cyberpunk": "cyberpunk",
    "medieval": "medieval",
    "fantasy": "fantasy",
    "modern": "modern",
}

# Цвета HP-бара по теме
HP_COLORS = {
    "medieval": ("#c8c8b4", "#daa520", "#cc3333"),
    "cyberpunk": ("#7b68ee", "#00ced1", "#ff1493"),
    "post_apocalyptic": ("#8b7355", "#cd853f", "#8b0000"),
    "fantasy": ("#90ee90", "#ffd700", "#dc143c"),
    "modern": ("#d3d3d3", "#4682b4", "#dc143c"),
}


class StatusPanel(Static):
    """Боковая панель статуса персонажа."""

    def update_from_engine(self, engine: Engine, theme: str = "medieval") -> None:
        p = engine.player
        w = engine.world
        loc = w.locations.get(w.current_location_id)
        loc_name = loc.name if loc else w.current_location_id

        _, accent, danger = HP_COLORS.get(theme, HP_COLORS["medieval"])
        hp_pct = p.health / max(p.max_health, 1)
        hp_color = danger if hp_pct < 0.3 else accent
        hp_bar = self._hp_bar(p.health, p.max_health, width=12)

        # NPC в текущей локации
        npcs_here = [
            n.name for n in engine.npcs.values()
            if n.location_id == w.current_location_id and n.status == "alive"
        ]
        npcs_str = "\n".join(f"  · {n}" for n in npcs_here) or "  пусто"

        # Навыки — только ненулевые
        skills_lines = "\n".join(
            f"  {k:<12} [{self._skill_bar(v)}] {v}"
            for k, v in list(p.skills.items())[:6]
            if v > 0
        )

        # Квесты
        quests_lines = "\n".join(
            f"  [{q.status[:3].upper()}] {q.title[:18]}"
            for q in p.active_quests[:5]
        ) or "  нет активных"

        # Репутация с NPC в локации
        rep_lines = ""
        for n in engine.npcs.values():
            if n.location_id == w.current_location_id and n.status == "alive":
                rep = p.reputation.get(n.id, 0)
                if rep != 0:
                    sign = "+" if rep > 0 else ""
                    rep_lines += f"\n  {n.name[:14]}: {sign}{rep}"

        gold = engine._parse_gold()

        text = (
            f"[bold]┌─ ПЕРСОНАЖ ──────────┐[/bold]\n"
            f"  [bold]{p.name}[/bold]\n"
            f"  HP [{hp_color}]{hp_bar}[/{hp_color}] {p.health}/{p.max_health}\n"
            f"  Золото: [yellow]{gold}[/yellow]\n"
            f"\n[bold]├─ ЛОКАЦИЯ ───────────┤[/bold]\n"
            f"  {loc_name[:22]}\n"
            f"  [dim]{w._format_time()}[/dim]\n"
            f"\n[bold]├─ ЗДЕСЬ ─────────────┤[/bold]\n"
            f"{npcs_str}\n"
            f"\n[bold]├─ НАВЫКИ ────────────┤[/bold]\n"
            f"{skills_lines}\n"
        )
        if quests_lines != "  нет активных":
            text += f"\n[bold]├─ КВЕСТЫ ────────────┤[/bold]\n{quests_lines}\n"
        if rep_lines:
            text += f"\n[bold]├─ РЕПУТАЦИЯ ─────────┤[/bold]{rep_lines}\n"
        text += f"\n[bold]└─────────────────────┘[/bold]"

        self.update(text)

    @staticmethod
    def _hp_bar(hp: int, max_hp: int, width: int = 12) -> str:
        if max_hp <= 0:
            return "░" * width
        filled = round((hp / max_hp) * width)
        return "█" * filled + "░" * (width - filled)

    @staticmethod
    def _skill_bar(val: int, width: int = 5) -> str:
        filled = round((min(val, 100) / 100) * width)
        return "▪" * filled + "·" * (width - filled)


class EchoSimApp(App):
    """Главное приложение TUI Echo-Sim."""

    CSS_PATH = "tui.tcss"

    BINDINGS = [
        ("ctrl+s", "save_game", "Сохранить"),
        ("ctrl+l", "load_game", "Загрузить"),
        ("escape", "focus_input", "Ввод"),
        ("ctrl+c", "quit", "Выход"),
    ]

    def __init__(self, engine: Engine) -> None:
        super().__init__()
        self.engine = engine
        self._theme = EPOCH_THEMES.get(engine.world.epoch.lower(), "modern")
        self._cmd_history: list[str] = []
        self._history_idx: int = -1
        self.add_class(f"theme-{self._theme}")

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            with Vertical(id="left-panel"):
                yield RichLog(id="narrative", highlight=False, markup=True, wrap=True, min_width=40)
                yield Static("", id="status-bar")
                yield Input(placeholder="▶  введите команду...", id="command-input")
            yield StatusPanel(id="status-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._update_status()
        self._print_welcome()
        self.query_one("#command-input", Input).focus()

    def _print_welcome(self) -> None:
        e = self.engine
        loc = e.world.locations.get(e.world.current_location_id)
        loc_name = loc.name if loc else ""
        self._narrative_separator("ECHO-SIM", color="bold green")
        self.append_narrative(
            f"[bold]{e.player.name}[/bold] · {e.world.epoch} · {loc_name}\n"
            f"[dim]Пиши что делаешь, или введи 'помощь' для списка команд.[/dim]"
        )
        self._narrative_separator()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        if not command:
            return
        # История команд
        if not self._cmd_history or self._cmd_history[-1] != command:
            self._cmd_history.append(command)
        self._history_idx = -1

        event.input.value = ""
        event.input.disabled = True

        # Для встроенных команд не показываем индикатор генерации
        _fast = ("look", "осмотр", "где я", "инвентарь", "вещи", "статус",
                 "помощь", "help", "магазин", "shop", "сохранить", "загрузить")
        if not any(command.lower().startswith(c) for c in _fast):
            self._set_status_bar("⏳ генерация...")

        self.append_narrative(f"\n[bold]▶[/bold] [italic]{command}[/italic]")
        self._run_command(command)

    @work(exclusive=True, thread=True)
    def _run_command(self, command: str) -> None:
        """Выполнить команду в отдельном потоке со стримингом."""
        status_buf: list[str] = []

        def on_token(token: str) -> None:
            status_buf.append(token)
            # Обновляем status-bar каждые ~40 символов — живой индикатор генерации
            if len(status_buf) >= 40 or token in ("\n", ".", "!", "?"):
                preview = "".join(status_buf)[-60:].replace("\n", " ")
                self.call_from_thread(self._set_status_bar, f"[dim]{preview}…[/dim]")
                status_buf.clear()

        self.engine.gm.stream_callback = on_token
        result = ""
        try:
            result = self.engine.process_command(command)
        except SystemExit:
            self.call_from_thread(self.append_narrative, "[bold red]До свидания![/bold red]")
            self.call_from_thread(self.exit)
            return
        finally:
            self.engine.gm.stream_callback = None

        # result — уже распарсенный нарратив (без JSON-обёртки)
        if result.strip():
            self.call_from_thread(self.append_narrative, result.strip())

        self.call_from_thread(self._narrative_separator)
        self.call_from_thread(self._update_status)
        self.call_from_thread(self._set_status_bar, "")

        # Показать накопленные ambient-события
        ambient_events = list(self.engine._pending_ambient)
        self.engine._pending_ambient.clear()
        for amb in ambient_events:
            self.call_from_thread(self._show_ambient, amb)

        if self.engine.state == "game_over":
            self.call_from_thread(self.handle_game_over)
        else:
            inp = self.query_one("#command-input", Input)
            self.call_from_thread(setattr, inp, "disabled", False)
            self.call_from_thread(inp.focus)
    def on_key(self, event) -> None:
        inp = self.query_one("#command-input", Input)
        # История команд стрелками
        if event.key == "up" and self._cmd_history:
            self._history_idx = max(0, (
                len(self._cmd_history) - 1
                if self._history_idx == -1
                else self._history_idx - 1
            ))
            inp.value = self._cmd_history[self._history_idx]
            inp.cursor_position = len(inp.value)
        elif event.key == "down" and self._cmd_history:
            if self._history_idx == -1:
                return
            self._history_idx += 1
            if self._history_idx >= len(self._cmd_history):
                self._history_idx = -1
                inp.value = ""
            else:
                inp.value = self._cmd_history[self._history_idx]
                inp.cursor_position = len(inp.value)

        if self.engine.state == "game_over":
            if event.key == "r":
                self.engine.reset()
                inp.disabled = False
                inp.placeholder = "▶  введите команду..."
                inp.focus()
                self._narrative_separator("НОВАЯ ИГРА", color="bold green")
                self._update_status()
            elif event.key == "q":
                self.exit()

    def append_narrative(self, text: str) -> None:
        self.query_one("#narrative", RichLog).write(text)

    def _narrative_separator(self, label: str = "", color: str = "dim") -> None:
        log = self.query_one("#narrative", RichLog)
        if label:
            pad = max(0, (46 - len(label) - 2) // 2)
            line = "─" * pad + f" {label} " + "─" * pad
        else:
            line = "─" * 48
        log.write(f"[{color}]{line}[/{color}]")

    def _set_status_bar(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(text)

    def _show_ambient(self, text: str) -> None:
        """Показать фоновое событие — курсивом, отдельным блоком."""
        log = self.query_one("#narrative", RichLog)
        log.write(f"[dim italic]  ✦ {text}[/dim italic]")

    def _update_status(self) -> None:
        self.query_one("#status-panel", StatusPanel).update_from_engine(
            self.engine, self._theme
        )

    def handle_game_over(self) -> None:
        inp = self.query_one("#command-input", Input)
        inp.disabled = True
        inp.placeholder = "Игра окончена · R — рестарт · Q — выход"
        self._narrative_separator("ИГРА ОКОНЧЕНА", color="bold red")
        self.append_narrative(
            "[bold red]Ты погиб.[/bold red]\n"
            "[dim]Нажми [bold]R[/bold] для рестарта или [bold]Q[/bold] для выхода.[/dim]"
        )

    def action_save_game(self) -> None:
        self.engine.save_game()
        self._set_status_bar("[green]✓ Сохранено[/green]")
        self.set_timer(2, lambda: self._set_status_bar(""))

    def action_load_game(self) -> None:
        if self.engine.load_game():
            self._set_status_bar("[green]✓ Загружено[/green]")
            self._update_status()
            self._narrative_separator("ИГРА ЗАГРУЖЕНА", color="bold green")
        else:
            self._set_status_bar("[red]✗ Файл сохранения не найден[/red]")
        self.set_timer(2, lambda: self._set_status_bar(""))

    def action_focus_input(self) -> None:
        self.query_one("#command-input", Input).focus()
