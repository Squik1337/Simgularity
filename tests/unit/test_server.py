"""Unit-тесты для HTTP-сервера."""
import json
import sys
import os
import time
import threading
import urllib.request
import urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from tests.conftest import minimal_config
from echo_sim.core.engine import Engine
from echo_sim.server import GameServer


@pytest.fixture(scope="module")
def server_engine(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("server")
    cfg_file = tmp_path / "world.json"
    cfg_file.write_text(json.dumps(minimal_config()), encoding="utf-8")
    engine = Engine(str(cfg_file))
    return engine


@pytest.fixture(scope="module")
def running_server(server_engine):
    server = GameServer(server_engine, port=18080)
    server.start()
    time.sleep(0.2)  # дать серверу запуститься
    yield server
    server.stop()


def http_get(path: str, port: int = 18080) -> tuple[int, dict]:
    url = f"http://localhost:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def http_post(path: str, data: dict, port: int = 18080) -> tuple[int, dict]:
    url = f"http://localhost:{port}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def http_post_raw(path: str, raw: bytes, port: int = 18080) -> tuple[int, dict]:
    url = f"http://localhost:{port}{path}"
    req = urllib.request.Request(url, data=raw, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def test_get_state(running_server):
    status, data = http_get("/state")
    assert status == 200
    assert "world" in data
    assert "player" in data


def test_post_command_look(running_server):
    status, data = http_post("/command", {"command": "look"})
    assert status == 200
    assert "response" in data
    assert "state" in data


def test_post_command_invalid_json(running_server):
    status, data = http_post_raw("/command", b"not valid json {{{")
    assert status == 400
    assert "error" in data


def test_post_reset(running_server):
    status, data = http_post("/reset", {})
    assert status == 200
    assert data.get("status") == "ok"
    assert "state" in data


def test_content_type_header(running_server):
    url = "http://localhost:18080/state"
    with urllib.request.urlopen(url, timeout=5) as resp:
        ct = resp.headers.get("Content-Type", "")
        assert "application/json" in ct
