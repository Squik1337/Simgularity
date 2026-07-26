# -*- coding: utf-8 -*-
"""Доменные исключения Echo-Sim."""
from __future__ import annotations


class EchoSimError(Exception):
    """Базовое исключение проекта."""


class LLMError(EchoSimError):
    """Ошибка обращения к LLM-провайдеру."""


class LLMUnavailableError(LLMError):
    """LLM-провайдер недоступен (сеть, отключённый сервис, HTTP-ошибка)."""


class LLMTimeoutError(LLMError):
    """Превышено время ожидания ответа LLM."""


class SaveGameError(EchoSimError):
    """Ошибка чтения или записи файла сохранения."""
