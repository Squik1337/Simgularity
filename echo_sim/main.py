"""Точка входа Echo-Sim — CLI REPL и TUI."""
import argparse
import sys
import os

# Добавить корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from echo_sim.core.engine import Engine


def run_cli(engine: Engine) -> None:
    """Запустить интерактивный CLI REPL."""
    print(engine._start_message())
    print()
    while True:
        try:
            command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break
        if not command:
            continue
        try:
            response = engine.process_command(command)
            print(response)
            print()
        except SystemExit:
            print("До свидания!")
            break


def run_tui(engine: Engine) -> None:
    """Запустить TUI на базе Textual."""
    try:
        from echo_sim.tui import EchoSimApp
        app = EchoSimApp(engine)
        app.run()
    except ImportError:
        print("Ошибка: библиотека 'textual' не установлена. Запустите: pip install textual")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Echo-Sim — текстовая симуляция жизни с LLM")
    parser.add_argument(
        "--config",
        default="echo_sim/config/world.json",
        help="Путь к файлу конфигурации мира (по умолчанию: echo_sim/config/world.json)",
    )
    parser.add_argument(
        "--ui",
        choices=["cli", "tui"],
        default="cli",
        help="Режим интерфейса: cli (по умолчанию) или tui",
    )
    args = parser.parse_args()

    engine = Engine(config_path=args.config)

    if args.ui == "tui":
        run_tui(engine)
    else:
        run_cli(engine)


if __name__ == "__main__":
    main()
