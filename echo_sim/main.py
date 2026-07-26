"""Точка входа Echo-Sim — CLI REPL и TUI."""
import argparse
import logging
import sys
import os

# Добавить корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from echo_sim.core.engine import Engine

logger = logging.getLogger(__name__)


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
        except SystemExit:
            print("До свидания!")
            break
        except Exception as e:
            logger.exception("Ошибка при выполнении команды %r", command)
            print(f"Ошибка: {type(e).__name__}: {e}")
            print()
            continue
        print(response)
        print()


def run_tui(engine: Engine) -> None:
    """Запустить TUI на базе Textual."""
    try:
        from echo_sim.tui import EchoSimApp
    except ImportError as e:
        logger.debug("Импорт TUI не удался", exc_info=True)
        print(f"Ошибка: не удалось загрузить TUI ({e}). Запустите: pip install textual")
        sys.exit(1)
    app = EchoSimApp(engine)
    app.run()


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
    parser.add_argument(
        "--log-level",
        default=os.environ.get("ECHO_SIM_LOG_LEVEL", "WARNING"),
        help="Уровень логирования: DEBUG, INFO, WARNING, ERROR",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    engine = Engine(config_path=args.config)

    if args.ui == "tui":
        run_tui(engine)
    else:
        run_cli(engine)


if __name__ == "__main__":
    main()
