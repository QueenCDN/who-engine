"""Контракт парсера архива и общие помощники."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Protocol, Sequence

from ..domain import ArchiveRecord


class ArchiveParser(Protocol):
    """Разбирает один формат выгрузки в список сообщений."""

    suffix: str

    def parse(self, raw: str) -> list[ArchiveRecord]:
        ...


def content_identity(parts: Sequence[Any]) -> str:
    """Контентный адрес сообщения.

    Неизменённое сообщение получает тот же идентификатор в пересекающихся
    выгрузках, поэтому повторный импорт не создаёт дубликатов.
    """
    payload = json.dumps(list(parts), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def first_value(source: Mapping[str, Any], keys: Iterable[str],
                default: Any = '') -> Any:
    """Первое непустое значение из перечисленных ключей."""
    for key in keys:
        value = source.get(key)
        if value:
            return value
    return default


def text_of(value: Any) -> str:
    """Собирает текст из строки, списка частей или словаря-обёртки."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(text_of(item) for item in value if item is not None)
    if isinstance(value, dict):
        for key in ('text', 'content', 'body'):
            if key in value:
                return text_of(value[key])
    return ''


def as_list(value: Any) -> list[Any] | None:
    """Приводит список или словарь-коллекцию к списку; иначе None."""
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, list):
        return value
    return None
