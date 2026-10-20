"""Нормализованный TXT с заголовками `## N`, role, datetime, conversation_id."""
from __future__ import annotations

import re

from ..domain import ArchiveRecord
from .base import content_identity

HEADER = re.compile(
    r'^##\s+(\d+)\r?\n'
    r'role:\s*(user|assistant)\r?\n'
    r'datetime:\s*([^\r\n]+)\r?\n'
    r'conversation_id:\s*([^\r\n]+)\r?\n'
    r'\s*\r?\n',
    re.M,
)


class GrokTxtParser:
    """Текст между двумя заголовками считается телом первого сообщения."""

    suffix = '.txt'

    def parse(self, raw: str) -> list[ArchiveRecord]:
        headers = list(HEADER.finditer(raw))
        return [self._record(raw, headers, index)
                for index in range(len(headers))]

    @staticmethod
    def _record(raw: str, headers: list[re.Match], index: int) -> ArchiveRecord:
        header = headers[index]
        is_last = index + 1 >= len(headers)
        end = len(raw) if is_last else headers[index + 1].start()
        body = raw[header.end():end].strip()
        conversation_id = header.group(4).strip()
        at = header.group(3).strip()
        role = header.group(2)
        return ArchiveRecord(
            id=content_identity([conversation_id, at, role, body]),
            conversation_id=conversation_id,
            at=at,
            role=role,
            text=body,
        )
