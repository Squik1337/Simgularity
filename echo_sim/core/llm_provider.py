# -*- coding: utf-8 -*-
"""Абстракция для различных LLM провайдеров."""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Callable, Optional


class LLMProvider(ABC):
    """Базовый класс для LLM провайдеров."""

    def __init__(self, model: str, timeout: int = 120,
                 stream_callback: Optional[Callable[[str], None]] = None):
        self.model = model
        self.timeout = timeout
        self.stream_callback = stream_callback

    @abstractmethod
    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        """Генерировать ответ от LLM."""
        pass

    # ── Общие утилиты для HTTP-стриминга ──────────────────

    @staticmethod
    def _build_request(url: str, payload: dict,
                       extra_headers: Optional[dict] = None) -> urllib.request.Request:
        """Собрать POST-запрос с JSON-телом."""
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        data = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(url, data=data, headers=headers, method="POST")

    def _emit(self, token: str) -> None:
        """Отдать токен в callback или напечатать в stdout."""
        if self.stream_callback:
            self.stream_callback(token)
        else:
            print(token, end="", flush=True)

    def _finalize(self) -> None:
        """Завершить вывод переводом строки при печати в stdout."""
        if not self.stream_callback:
            print()

    def _stream(self, req: urllib.request.Request,
                parse_chunk: Callable[[bytes], tuple[str, bool]]) -> str:
        """Отправить запрос и построчно стримить ответ.

        parse_chunk(line) -> (token, done): извлекает токен из строки ответа и
        сигнализирует о завершении потока.
        """
        result: list[str] = []
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            for line in resp:
                if not line.strip():
                    continue
                token, done = parse_chunk(line)
                if token:
                    result.append(token)
                    self._emit(token)
                if done:
                    break
        self._finalize()
        return "".join(result)


class OllamaProvider(LLMProvider):
    """Провайдер для локального Ollama."""
    
    def __init__(self, model: str, url: str = "http://localhost:11434/api/generate", 
                 timeout: int = 120, stream_callback: Optional[Callable[[str], None]] = None):
        super().__init__(model, timeout, stream_callback)
        self.url = url

    @staticmethod
    def _parse_chunk(line: bytes) -> tuple[str, bool]:
        try:
            chunk = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            return "", False
        return chunk.get("response", ""), bool(chunk.get("done"))

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        full_prompt = system_prompt + "\n\n"
        for msg in messages:
            role = "Igrok" if msg["role"] == "user" else "GM"
            full_prompt += f"{role}: {msg['content']}\n"

        req = self._build_request(self.url, {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
        })

        try:
            return self._stream(req, self._parse_chunk)
        except urllib.error.URLError:
            return "GM nedostupen: ollama ne zapushchen"
        except TimeoutError:
            return "GM nedostupen: prevysheno vremya ozhidaniya"
        except Exception as e:
            return f"GM nedostupen: {e}"


class OpenAICompatibleProvider(LLMProvider):
    """Провайдер для OpenAI API и совместимых (Groq, Together AI, LocalAI, vLLM, etc.)."""
    
    def __init__(self, model: str, api_key: str, api_url: str = "https://api.openai.com/v1/chat/completions",
                 timeout: int = 120, temperature: float = 0.7, max_tokens: int = 2048,
                 stream_callback: Optional[Callable[[str], None]] = None):
        super().__init__(model, timeout, stream_callback)
        self.api_key = api_key
        self.api_url = api_url
        self.temperature = temperature
        self.max_tokens = max_tokens

    @staticmethod
    def _parse_chunk(line: bytes) -> tuple[str, bool]:
        line_str = line.decode("utf-8")
        if not line_str.startswith("data: "):
            return "", False
        data_str = line_str[6:]
        if data_str.strip() == "[DONE]":
            return "", True
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            return "", False
        delta = chunk.get("choices", [{}])[0].get("delta", {})
        return delta.get("content", ""), False

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        # Формируем сообщения в формате OpenAI
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(messages)

        req = self._build_request(
            self.api_url,
            {
                "model": self.model,
                "messages": openai_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            },
            extra_headers={"Authorization": f"Bearer {self.api_key}"},
        )

        try:
            return self._stream(req, self._parse_chunk)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return f"GM nedostupen: HTTP {e.code} - {error_body}"
        except urllib.error.URLError as e:
            return f"GM nedostupen: {e.reason}"
        except TimeoutError:
            return "GM nedostupen: prevysheno vremya ozhidaniya"
        except Exception as e:
            return f"GM nedostupen: {e}"


def create_llm_provider(config: dict, stream_callback: Optional[Callable[[str], None]] = None) -> LLMProvider:
    """Фабричная функция для создания провайдера на основе конфигурации."""
    provider_type = config.get("llm_provider", "ollama").lower()
    model = config.get("llm_model", "llama3")
    
    if provider_type == "ollama":
        return OllamaProvider(
            model=model,
            url=config.get("ollama_url", "http://localhost:11434/api/generate"),
            timeout=config.get("llm_timeout", 120),
            stream_callback=stream_callback,
        )
    elif provider_type in ("openai", "groq", "together", "localai", "vllm", "openai_compatible", "kluster"):
        api_key = config.get("api_key")
        if not api_key:
            raise ValueError(f"API ключ не указан для провайдера {provider_type}")
        
        # URL по умолчанию для разных провайдеров
        default_urls = {
            "openai": "https://api.openai.com/v1/chat/completions",
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "together": "https://api.together.xyz/v1/chat/completions",
            "localai": "http://localhost:8080/v1/chat/completions",
            "vllm": "http://localhost:8000/v1/chat/completions",
            "kluster": "https://api.kluster.ai/v1/chat/completions",
        }
        
        api_url = config.get("api_url", default_urls.get(provider_type, "https://api.openai.com/v1/chat/completions"))
        
        return OpenAICompatibleProvider(
            model=model,
            api_key=api_key,
            api_url=api_url,
            timeout=config.get("llm_timeout", 120),
            temperature=config.get("llm_temperature", 0.7),
            max_tokens=config.get("llm_max_tokens", 2048),
            stream_callback=stream_callback,
        )
    else:
        raise ValueError(f"Неизвестный тип провайдера: {provider_type}")
