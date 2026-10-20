"""Узкие контракты хранилища.

Сервисы зависят только от нужного им протокола, а не от всей базы (ISP),
поэтому в тестах подменяется одна таблица, а не целое соединение.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from ..domain import (ArchiveMetadata, ArchiveRecord, ConversationSummary, Note,
                      Role, Run, SourceHit, SourceMessage, Turn, TurnStatus)


class RunRepository(Protocol):
    def create_run(self, title: str, arm: str, model: str) -> str:
        ...

    def list_runs(self) -> list[Run]:
        ...

    def delete_run(self, run_id: str) -> None:
        ...

    def run_size(self, run_id: str) -> tuple[int, int]:
        ...


class TurnRepository(Protocol):
    def add_turn(self, run_id: str, role: Role, content: str,
                 status: TurnStatus, model: str = '',
                 usage: Mapping[str, Any] | None = None,
                 error: str = '', request_id: str = '') -> str:
        ...

    def list_turns(self, run_id: str) -> list[Turn]:
        ...

    def update_turn(self, turn_id: str, status: TurnStatus,
                    content: str | None = None, error: str | None = None,
                    model: str | None = None,
                    usage: Mapping[str, Any] | None = None) -> None:
        ...


class NoteRepository(Protocol):
    def add_note(self, run_id: str, label: str, observation: str,
                 interpretation: str, confidence: str) -> None:
        ...

    def list_notes(self, run_id: str) -> list[Note]:
        ...


class SourceRepository(Protocol):
    def save_records(self, records: Sequence[ArchiveRecord]) -> int:
        ...

    def save_metadata(self, items: Sequence[ArchiveMetadata]) -> None:
        ...

    def count(self, conversation_id: str) -> int:
        ...

    def summaries(self, conversation_id: str) -> list[ConversationSummary]:
        ...

    def messages(self, conversation_id: str,
                 limit: int = 30) -> list[SourceMessage]:
        ...

    def search(self, conversation_id: str, query: str,
               limit: int = 20) -> list[SourceHit]:
        ...


class ExportRepository(Protocol):
    def export_run(self, run_id: str) -> str:
        ...


class BackupRepository(Protocol):
    def backup(self) -> Path:
        ...
