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
    
    def __init__(self, model: str, stream_callback: Optional[Callable[[str], None]] = None):
        self.model = model
        self.stream_callback = stream_callback
    
    @abstractmethod
    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        """Генерировать ответ от LLM."""
        pass


class OllamaProvider(LLMProvider):
    """Провайдер для локального Ollama."""
    
    def __init__(self, model: str, url: str = "http://localhost:11434/api/generate", 
                 timeout: int = 120, stream_callback: Optional[Callable[[str], None]] = None):
        super().__init__(model, stream_callback)
        self.url = url
        self.timeout = timeout
    
    def generate(self, system_prompt: str, messages: list[dict]) -> str:
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
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            result = []
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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


class OpenAICompatibleProvider(LLMProvider):
    """Провайдер для OpenAI API и совместимых (Groq, Together AI, LocalAI, vLLM, etc.)."""
    
    def __init__(self, model: str, api_key: str, api_url: str = "https://api.openai.com/v1/chat/completions",
                 timeout: int = 120, temperature: float = 0.7, max_tokens: int = 2048,
                 stream_callback: Optional[Callable[[str], None]] = None):
        super().__init__(model, stream_callback)
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        # Формируем сообщения в формате OpenAI
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(messages)
        
        payload = json.dumps({
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }).encode("utf-8")
        
        req = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        
        try:
            result = []
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                result.append(token)
                                if self.stream_callback:
                                    self.stream_callback(token)
                                else:
                                    print(token, end="", flush=True)
                        except json.JSONDecodeError:
                            continue
            if not self.stream_callback:
                print()
            return "".join(result)
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
