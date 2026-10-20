"""Реализация хранилища на SQLite."""
from __future__ import annotations

import datetime
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from ..domain import (Arm, ArchiveMetadata, ArchiveRecord, ConversationSummary,
                      Note, Role, Run, SourceHit, SourceMessage, Turn,
                      TurnStatus)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(
    id TEXT PRIMARY KEY, created TEXT, title TEXT, arm TEXT, model TEXT);
CREATE TABLE IF NOT EXISTS turns(
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, created TEXT, role TEXT,
    content TEXT, status TEXT, request_id TEXT, model TEXT, usage_json TEXT,
    error TEXT, FOREIGN KEY(run_id) REFERENCES runs(id));
CREATE TABLE IF NOT EXISTS notes(
    id TEXT PRIMARY KEY, created TEXT, run_id TEXT, label TEXT,
    observation TEXT, interpretation TEXT, confidence TEXT);
CREATE TABLE IF NOT EXISTS source_messages(
    id TEXT PRIMARY KEY, conversation_id TEXT, at TEXT, role TEXT, text TEXT);
CREATE INDEX IF NOT EXISTS idx_source_at ON source_messages(at);
CREATE TABLE IF NOT EXISTS source_metadata(
    message_id TEXT PRIMARY KEY, raw_id TEXT, parent_id TEXT, model TEXT,
    path_json TEXT, FOREIGN KEY(message_id) REFERENCES source_messages(id));
CREATE INDEX IF NOT EXISTS idx_turn_run ON turns(run_id, created);
'''


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class SqliteRepository:
    """Единое соединение с базой; сервисы видят только нужные им протоколы."""

    def __init__(self, path: Path, timeout: int = 30) -> None:
        self._path = Path(path)
        self._timeout = timeout
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=self._timeout)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def init(self) -> None:
        with self._connection() as connection:
            connection.executescript(SCHEMA)

    # --- runs ---------------------------------------------------------------

    def create_run(self, title: str, arm: str, model: str) -> str:
        run_id = str(uuid.uuid4())
        with self._connection() as connection:
            connection.execute(
                'INSERT INTO runs(id, created, title, arm, model) '
                'VALUES(?,?,?,?,?)',
                (run_id, utc_now(), title, arm, model))
        return run_id

    def list_runs(self) -> list[Run]:
        with self._connection() as connection:
            rows = connection.execute(
                'SELECT id, created, title, arm, model FROM runs '
                'ORDER BY created DESC').fetchall()
        return [Run(row[0], row[1], row[2], Arm.from_label(row[3]), row[4])
                for row in rows]

    # --- turns --------------------------------------------------------------

    def add_turn(self, run_id: str, role: Role, content: str,
                 status: TurnStatus = TurnStatus.COMPLETE, model: str = '',
                 usage: Mapping[str, Any] | None = None,
                 error: str = '', request_id: str = '') -> str:
        turn_id = str(uuid.uuid4())
        with self._connection() as connection:
            connection.execute(
                'INSERT INTO turns(id, run_id, created, role, content, status, '
                'request_id, model, usage_json, error) '
                'VALUES(?,?,?,?,?,?,?,?,?,?)',
                (turn_id, run_id, utc_now(), role.value, content, status.value,
                 request_id, model,
                 json.dumps(dict(usage or {}), ensure_ascii=False), error))
        return turn_id

    def list_turns(self, run_id: str) -> list[Turn]:
        with self._connection() as connection:
            rows = connection.execute(
                'SELECT id, role, content, status, created, model, error '
                'FROM turns WHERE run_id=? ORDER BY created, rowid',
                (run_id,)).fetchall()
        return [self._turn(row) for row in rows]

    @staticmethod
    def _turn(row: Sequence[Any]) -> Turn:
        return Turn(
            id=row[0],
            role=Role.parse(row[1]) or Role.ASSISTANT,
            content=row[2] or '',
            status=TurnStatus(row[3]),
            created=row[4] or '',
            model=row[5] or '',
            error=row[6] or '',
        )

    def update_turn(self, turn_id: str, status: TurnStatus,
                    content: str | None = None, error: str | None = None,
                    model: str | None = None,
                    usage: Mapping[str, Any] | None = None) -> None:
        updates: dict[str, Any] = {'status': status.value}
        optional = {
            'content': content,
            'error': error,
            'model': model,
            'usage_json': (json.dumps(dict(usage), ensure_ascii=False)
                           if usage is not None else None),
        }
        updates.update({name: value for name, value in optional.items()
                        if value is not None})
        assignments = ', '.join(f'{name}=?' for name in updates)
        with self._connection() as connection:
            connection.execute(
                f'UPDATE turns SET {assignments} WHERE id=?',
                (*updates.values(), turn_id))

    # --- notes --------------------------------------------------------------

    def add_note(self, run_id: str, label: str, observation: str,
                 interpretation: str, confidence: str) -> None:
        with self._connection() as connection:
            connection.execute(
                'INSERT INTO notes(id, created, run_id, label, observation, '
                'interpretation, confidence) VALUES(?,?,?,?,?,?,?)',
                (str(uuid.uuid4()), utc_now(), run_id, label, observation,
                 interpretation, confidence))

    def list_notes(self, run_id: str) -> list[Note]:
        with self._connection() as connection:
            rows = connection.execute(
                'SELECT created, label, observation, interpretation, confidence '
                'FROM notes WHERE run_id=? ORDER BY created',
                (run_id,)).fetchall()
        return [Note(*row) for row in rows]

    # --- архив --------------------------------------------------------------

    def save_records(self, records: Sequence[ArchiveRecord]) -> int:
        """Возвращает число действительно новых сообщений."""
        with self._connection() as connection:
            before = connection.total_changes
            connection.executemany(
                'INSERT OR IGNORE INTO source_messages'
                '(id, conversation_id, at, role, text) VALUES(?,?,?,?,?)',
                [record.as_row() for record in records])
            return connection.total_changes - before

    def save_metadata(self, items: Sequence[ArchiveMetadata]) -> None:
        with self._connection() as connection:
            connection.executemany(
                'INSERT OR IGNORE INTO source_metadata'
                '(message_id, raw_id, parent_id, model, path_json) '
                'VALUES(?,?,?,?,?)',
                [item.as_row() for item in items])

    def count(self, conversation_id: str) -> int:
        with self._connection() as connection:
            return connection.execute(
                'SELECT COUNT(*) FROM source_messages WHERE conversation_id=?',
                (conversation_id,)).fetchone()[0]

    def summaries(self, conversation_id: str) -> list[ConversationSummary]:
        with self._connection() as connection:
            rows = connection.execute(
                'SELECT conversation_id, COUNT(*), MIN(at), MAX(at) '
                'FROM source_messages WHERE conversation_id=? '
                'GROUP BY conversation_id',
                (conversation_id,)).fetchall()
        return [ConversationSummary(row[0], row[1], row[2] or '', row[3] or '')
                for row in rows]

    def messages(self, conversation_id: str,
                 limit: int = 30) -> list[SourceMessage]:
        with self._connection() as connection:
            rows = connection.execute(
                'SELECT at, role, text FROM source_messages '
                'WHERE conversation_id=? ORDER BY at LIMIT ?',
                (conversation_id, limit)).fetchall()
        return [SourceMessage(*row) for row in rows]

    def search(self, conversation_id: str, query: str,
               limit: int = 20) -> list[SourceHit]:
        term = query.strip()
        if not term:
            return []
        with self._connection() as connection:
            rows = connection.execute(
                'SELECT id, at, role, substr(text, 1, 1600) '
                'FROM source_messages WHERE conversation_id=? AND text LIKE ? '
                'ORDER BY at LIMIT ?',
                (conversation_id, f'%{term}%', limit)).fetchall()
        return [SourceHit(*row) for row in rows]

    # --- экспорт и резервная копия -----------------------------------------

    def export_run(self, run_id: str) -> str:
        with self._connection() as connection:
            payload = {
                'run': connection.execute(
                    'SELECT * FROM runs WHERE id=?', (run_id,)).fetchone(),
                'turns': connection.execute(
                    'SELECT * FROM turns WHERE run_id=? ORDER BY created, rowid',
                    (run_id,)).fetchall(),
                'notes': connection.execute(
                    'SELECT * FROM notes WHERE run_id=?', (run_id,)).fetchall(),
            }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def backup(self) -> Path:
        """Соединения закрываются явно: иначе Windows держит файл копии."""
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        target = self._path.parent / f'backup_{stamp}.sqlite3'
        source = sqlite3.connect(self._path)
        try:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
        return target
