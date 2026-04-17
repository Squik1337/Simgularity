"""HTTP-сервер для интеграции с Godot-фронтендом."""
from __future__ import annotations
import json
import sys
import os
import threading
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if TYPE_CHECKING:
    from echo_sim.core.engine import Engine


class GameRequestHandler(BaseHTTPRequestHandler):
    engine: Engine  # устанавливается через server.engine

    def log_message(self, format, *args):
        pass  # Отключить стандартный лог

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Preflight CORS для Godot/браузеров."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_json_body(self) -> tuple[dict | None, str | None]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8")), None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return None, str(e)

    def do_POST(self):
        engine: Engine = self.server.engine  # type: ignore

        if self.path == "/command":
            body, err = self._read_json_body()
            if err or body is None:
                self._send_json({"error": f"Invalid JSON: {err}"}, 400)
                return
            command = body.get("command", "")
            if not isinstance(command, str):
                self._send_json({"error": "Field 'command' must be a string"}, 400)
                return
            try:
                response = engine.process_command(command)
            except SystemExit:
                response = "Сервер продолжает работу. Используйте /reset для сброса."
            self._send_json({"response": response, "state": engine.get_full_state()})

        elif self.path == "/stream":
            # SSE-стриминг: токены идут сразу, финальный state — в конце
            body, err = self._read_json_body()
            if err or body is None:
                self._send_json({"error": f"Invalid JSON: {err}"}, 400)
                return
            command = body.get("command", "")
            if not isinstance(command, str):
                self._send_json({"error": "Field 'command' must be a string"}, 400)
                return
            self._stream_command(engine, command)

        elif self.path == "/reset":
            engine.reset()
            self._send_json({"status": "ok", "state": engine.get_full_state()})

        else:
            self._send_json({"error": "Not found"}, 404)

    def _stream_command(self, engine, command: str) -> None:
        """Стриминг ответа через chunked transfer — токены идут сразу."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        token_buf = []

        def on_token(token: str) -> None:
            token_buf.append(token)
            # Флашим каждые ~20 символов или на знаках препинания
            if len(token_buf) >= 20 or token in (".", "!", "?", "\n", ","):
                chunk = "".join(token_buf)
                token_buf.clear()
                try:
                    encoded = chunk.encode("utf-8")
                    self.wfile.write(f"{len(encoded):x}\r\n".encode())
                    self.wfile.write(encoded)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                except Exception:
                    pass

        engine.gm.stream_callback = on_token
        try:
            engine.process_command(command)
        except SystemExit:
            pass
        finally:
            engine.gm.stream_callback = None

        # Флашим остаток
        if token_buf:
            chunk = "".join(token_buf)
            encoded = chunk.encode("utf-8")
            try:
                self.wfile.write(f"{len(encoded):x}\r\n".encode())
                self.wfile.write(encoded)
                self.wfile.write(b"\r\n")
            except Exception:
                pass

        # Финальный чанк — state в JSON после разделителя
        try:
            state_json = json.dumps({"__state__": engine.get_full_state()}, ensure_ascii=False)
            encoded = state_json.encode("utf-8")
            self.wfile.write(f"{len(encoded):x}\r\n".encode())
            self.wfile.write(encoded)
            self.wfile.write(b"\r\n")
            # Завершающий chunked-терминатор
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except Exception:
            pass

    def do_GET(self):
        engine: Engine = self.server.engine  # type: ignore

        if self.path == "/state":
            self._send_json(engine.get_full_state())
        else:
            self._send_json({"error": "Not found"}, 404)


class _GameHTTPServer(HTTPServer):
    def __init__(self, server_address, handler, engine: Engine):
        super().__init__(server_address, handler)
        self.engine = engine


class GameServer:
    def __init__(self, engine: Engine, port: int = 8080) -> None:
        self.engine = engine
        self.port = port
        self._server: _GameHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._server = _GameHTTPServer(("", self.port), GameRequestHandler, self.engine)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"Echo-Sim сервер запущен на http://localhost:{self.port}")

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Echo-Sim HTTP Server")
    parser.add_argument("--config", default="echo_sim/config/world.json")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    from echo_sim.core.engine import Engine
    engine = Engine(config_path=args.config)
    port = args.port or engine.config.get("server_port", 8080)

    server = GameServer(engine, port=port)
    server.start()
    print(f"Мир: {engine.world.epoch} | Персонаж: {engine.player.name}")
    print("Нажмите Ctrl+C для остановки.")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка сервера...")
        server.stop()


if __name__ == "__main__":
    main()
