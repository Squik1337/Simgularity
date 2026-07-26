"""Тесты обработки ошибок: ошибки логируются и пробрасываются, а не глотаются."""
import json
import os
import sys
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import patch

from tests.conftest import minimal_config
from echo_sim.core.engine import Engine
from echo_sim.core.errors import LLMTimeoutError, LLMUnavailableError, SaveGameError
from echo_sim.core.gm import GameMaster
from echo_sim.core.llm_provider import OllamaProvider, OpenAICompatibleProvider


@pytest.fixture
def engine(tmp_path):
    config_path = tmp_path / "world.json"
    config_path.write_text(json.dumps(minimal_config()), encoding="utf-8")
    return Engine(config_path=str(config_path))


def test_ollama_unavailable_raises():
    provider = OllamaProvider(model="llama3")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(LLMUnavailableError):
            provider.generate("system", [])


def test_ollama_timeout_raises():
    provider = OllamaProvider(model="llama3")
    with patch("urllib.request.urlopen", side_effect=TimeoutError()):
        with pytest.raises(LLMTimeoutError):
            provider.generate("system", [])


def test_openai_http_error_includes_status():
    provider = OpenAICompatibleProvider(model="gpt-4o", api_key="k")
    err = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMUnavailableError, match="429"):
            provider.generate("system", [])


def test_gm_generate_returns_error_narrative_on_llm_failure():
    gm = GameMaster(minimal_config())
    with patch.object(gm.llm_provider, "generate", side_effect=LLMUnavailableError("нет связи")):
        response = gm.generate({}, "осмотреться")
    assert "нет связи" in response.narrative
    assert response.events == []


def test_ambient_llm_failure_does_not_break_tick(engine):
    with patch.object(engine.gm, "generate_ambient", side_effect=LLMUnavailableError("нет связи")):
        engine._try_ambient_event()
    assert engine._pending_ambient == []


def test_load_game_missing_file_returns_false(engine, tmp_path):
    assert engine.load_game(str(tmp_path / "нет-такого.json")) is False


def test_load_game_corrupted_file_raises(engine, tmp_path):
    save = tmp_path / "savegame.json"
    save.write_text("{не json", encoding="utf-8")
    with pytest.raises(SaveGameError):
        engine.load_game(str(save))


def test_load_command_reports_corrupted_save(engine, tmp_path):
    save = tmp_path / "savegame.json"
    save.write_text("{не json", encoding="utf-8")
    result = engine.process_command(f"load {save}")
    assert "Не удалось загрузить игру" in result


def test_save_game_unwritable_path_raises(engine, tmp_path):
    unwritable = tmp_path / "нет-каталога" / "savegame.json"
    with pytest.raises(SaveGameError):
        engine.save_game(str(unwritable))


def test_save_command_reports_failure(engine, tmp_path):
    unwritable = tmp_path / "нет-каталога" / "savegame.json"
    result = engine.process_command(f"save {unwritable}")
    assert "Не удалось сохранить игру" in result
