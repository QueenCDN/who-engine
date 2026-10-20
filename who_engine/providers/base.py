"""Контракт провайдера модели и нормализация usage."""
from __future__ import annotations

from typing import Any, Callable, Protocol, Sequence

from ..domain import ChatMessage, ChatReply
from ..errors import ConfigurationError

SCALARS = (str, int, float, bool, type(None))


class ChatClient(Protocol):
    """Отправка одного запроса без скрытых автоповторов."""

    def complete(self, messages: Sequence[ChatMessage], model: str) -> ChatReply:
        ...


class NullChatClient:
    """Офлайн-режим: ключа нет, запросы невозможны."""

    def complete(self, messages: Sequence[ChatMessage], model: str) -> ChatReply:
        raise ConfigurationError('В .env отсутствует XAI_API_KEY')


def _from_model_dump(usage: Any) -> dict[str, Any]:
    return usage.model_dump(mode='json')


def _from_vars(usage: Any) -> dict[str, Any]:
    return {key: value for key, value in vars(usage).items()
            if isinstance(value, SCALARS)}


def _from_repr(usage: Any) -> dict[str, Any]:
    return {'repr': str(usage)}


# Порядок важен: от самого информативного представления к запасному.
USAGE_HANDLERS: tuple[tuple[Callable[[Any], bool], Callable[[Any], dict]], ...] = (
    (lambda usage: usage is None, lambda usage: {}),
    (lambda usage: hasattr(usage, 'model_dump'), _from_model_dump),
    (lambda usage: hasattr(usage, '__dict__'), _from_vars),
)


def normalize_usage(usage: Any) -> dict[str, Any]:
    """Приводит объект usage любого SDK к JSON-совместимому словарю."""
    for matches, extract in USAGE_HANDLERS:
        if matches(usage):
            return extract(usage)
    return _from_repr(usage)
