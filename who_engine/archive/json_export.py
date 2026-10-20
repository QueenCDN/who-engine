"""Разбор JSON-выгрузок.

Поддерживаются проверенные формы экспорта; при неизвестной структуре парсер
останавливается с ошибкой, а не угадывает содержание.
"""
from __future__ import annotations

import datetime
import json
from typing import Any, Mapping

from ..domain import ArchiveMetadata, ArchiveRecord
from ..errors import ArchiveFormatError
from .base import as_list, content_identity, first_value, text_of

CONVERSATION_KEYS = ('conversations', 'data', 'chats')
CONVERSATION_ID_KEYS = ('conversation_id', 'id', 'uuid')
MESSAGE_LIST_KEYS = ('responses', 'messages', 'items')
ROLE_KEYS = ('role', 'sender', 'author')
TIMESTAMP_KEYS = ('create_time', 'datetime', 'created_at', 'timestamp', 'createdAt')
CONTENT_KEYS = ('content', 'text', 'message')
SOURCE_ID_KEYS = ('_id', 'id')

ROLE_ALIASES: Mapping[str, str] = {
    'user': 'user',
    'human': 'user',
    'Human': 'user',
    'assistant': 'assistant',
    'ASSISTANT': 'assistant',
    'grok': 'assistant',
    'ai': 'assistant',
    'model': 'assistant',
}


def normalize_role(value: Any) -> str | None:
    """Приводит роль к 'user'/'assistant'; неизвестная роль даёт None."""
    if isinstance(value, dict):
        value = first_value(value, ('role', 'name'), default=None)
    if not isinstance(value, str):
        return None
    return ROLE_ALIASES.get(value)


def normalize_timestamp(value: Any) -> str:
    """Поддерживает строки и форму MongoDB {"$date": {"$numberLong": ...}}."""
    if not isinstance(value, dict):
        return str(value)
    millis = (value.get('$date') or {}).get('$numberLong')
    if not millis:
        return ''
    moment = datetime.datetime.fromtimestamp(
        int(millis) / 1000, datetime.timezone.utc)
    return moment.isoformat()


class GrokJsonParser:
    """Обходит conversations[] → responses[] → response."""

    suffix = '.json'

    def parse(self, raw: str) -> list[ArchiveRecord]:
        conversations = self._conversations(json.loads(raw))
        records: list[ArchiveRecord] = []
        for conversation in conversations:
            if not isinstance(conversation, dict):
                continue
            records.extend(self._records(conversation))
        if not records:
            raise ArchiveFormatError(
                'Сообщения не распознаны: сначала изучить реальную структуру экспорта')
        return records

    @staticmethod
    def _conversations(obj: Any) -> list[Any]:
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            found = as_list(first_value(obj, CONVERSATION_KEYS, default=None))
            if found is not None:
                return found
            if isinstance(obj.get('messages'), list):
                return [obj]
        raise ArchiveFormatError(
            'Неизвестная JSON-структура. Пришлите схему без личных данных.')

    def _records(self, conversation: dict) -> list[ArchiveRecord]:
        meta = conversation.get('conversation') or conversation
        conversation_id = str(first_value(meta, CONVERSATION_ID_KEYS))
        messages = as_list(first_value(conversation, MESSAGE_LIST_KEYS, default=None))
        if messages is None:
            return []
        records = []
        for message in messages:
            record = self._record(conversation_id, message)
            if record is not None:
                records.append(record)
        return records

    @staticmethod
    def _record(conversation_id: str, message: Any) -> ArchiveRecord | None:
        if not isinstance(message, dict):
            return None
        if isinstance(message.get('response'), dict):
            message = message['response']
        role = normalize_role(first_value(message, ROLE_KEYS, default=None))
        if role is None:
            return None
        at = normalize_timestamp(first_value(message, TIMESTAMP_KEYS))
        text = text_of(first_value(message, CONTENT_KEYS))
        # Устойчивый идентификатор ответа xAI предпочтительнее хеша текста:
        # одинаковый текст не считается дубликатом автоматически.
        source_id = first_value(message, SOURCE_ID_KEYS, default=None)
        identity = content_identity(
            [conversation_id, source_id or [at, role, text]])
        return ArchiveRecord(identity, conversation_id, at, role, text)


class XaiMetadataParser:
    """Дополнительные метаданные xAI. Исходный JSON остаётся первоисточником."""

    def parse(self, raw: str) -> list[ArchiveMetadata]:
        obj = json.loads(raw)
        result: list[ArchiveMetadata] = []
        for item in obj.get('conversations', []):
            meta = item.get('conversation') or item
            conversation_id = str(first_value(meta, ('id', 'conversation_id')))
            result.extend(self._entries(conversation_id, item))
        return result

    @staticmethod
    def _entries(conversation_id: str, item: dict) -> list[ArchiveMetadata]:
        entries = []
        for wrapper in item.get('responses', []):
            message = wrapper.get('response', wrapper)
            raw_id = first_value(message, SOURCE_ID_KEYS, default=None)
            if not raw_id:
                continue
            entries.append(ArchiveMetadata(
                message_id=content_identity([conversation_id, raw_id]),
                raw_id=str(raw_id),
                parent_id=str(message.get('parent_response_id') or ''),
                model=str(message.get('model') or ''),
                path_json=json.dumps(message.get('path') or [], ensure_ascii=False),
            ))
        return entries
