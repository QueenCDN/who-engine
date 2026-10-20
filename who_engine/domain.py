"""Предметная модель. Без зависимостей от Streamlit, SQLite и SDK."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import ValidationError


class Arm(Enum):
    """Экспериментальная группа. Значение — метка, хранимая в базе."""

    CLEAN = 'A — чистый'
    HISTORY = 'B — история'
    DESCRIPTION = 'C — описание'
    PROCEDURE_G3 = 'D — процедура G3'

    @property
    def label(self) -> str:
        return self.value

    @classmethod
    def labels(cls) -> tuple[str, ...]:
        return tuple(arm.value for arm in cls)

    @classmethod
    def from_label(cls, label: str) -> 'Arm':
        try:
            return cls(label)
        except ValueError as exc:
            raise ValidationError(f'Неизвестная группа: {label}') from exc


class Role(Enum):
    SYSTEM = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'

    @classmethod
    def dialogue(cls) -> tuple['Role', ...]:
        """Роли, которые переносятся в историю активного диалога."""
        return (cls.USER, cls.ASSISTANT)

    @classmethod
    def parse(cls, value: Any) -> 'Role | None':
        """Мягкий разбор: неизвестная роль даёт None, а не исключение."""
        try:
            return cls(str(value))
        except ValueError:
            return None


class TurnStatus(Enum):
    INFLIGHT = 'inflight'
    COMPLETE = 'complete'
    UNCERTAIN = 'uncertain'


class Confidence(Enum):
    LOW = 'низкая'
    MEDIUM = 'средняя'
    HIGH = 'высокая'

    @classmethod
    def labels(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)


NOTE_LABELS: tuple[str, ...] = (
    'G1', 'G3', 'G4', 'META-HOW', 'CONTROLEXAMPLE', 'UNCERTAIN', 'OTHER',
)


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {'role': self.role.value, 'content': self.content}


@dataclass(frozen=True)
class ChatReply:
    """Ответ провайдера. `model` — фактически отработавшая версия модели."""

    content: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str = ''


@dataclass(frozen=True)
class Run:
    id: str
    created: str
    title: str
    arm: Arm
    model: str

    @property
    def short_id(self) -> str:
        return self.id[:8]


@dataclass(frozen=True)
class Turn:
    id: str
    role: Role
    content: str
    status: TurnStatus
    created: str
    model: str = ''
    error: str = ''

    @property
    def is_complete(self) -> bool:
        return self.status is TurnStatus.COMPLETE

    @property
    def display_role(self) -> Role:
        """Системные/неизвестные реплики показываются как ответ ассистента."""
        return self.role if self.role in Role.dialogue() else Role.ASSISTANT


@dataclass(frozen=True)
class Note:
    created: str
    label: str
    observation: str
    interpretation: str
    confidence: str

    def as_tuple(self) -> tuple[str, str, str, str, str]:
        return (self.created, self.label, self.observation,
                self.interpretation, self.confidence)


@dataclass(frozen=True)
class ArchiveRecord:
    """Сообщение из импортированного архива. `id` — контентный хеш."""

    id: str
    conversation_id: str
    at: str
    role: str
    text: str

    def as_row(self) -> tuple[str, str, str, str, str]:
        return (self.id, self.conversation_id, self.at, self.role, self.text)


@dataclass(frozen=True)
class ArchiveMetadata:
    message_id: str
    raw_id: str
    parent_id: str
    model: str
    path_json: str

    def as_row(self) -> tuple[str, str, str, str, str]:
        return (self.message_id, self.raw_id, self.parent_id,
                self.model, self.path_json)


@dataclass(frozen=True)
class SourceMessage:
    at: str
    role: str
    text: str


@dataclass(frozen=True)
class ConversationSummary:
    conversation_id: str
    message_count: int
    earliest: str
    latest: str


@dataclass(frozen=True)
class SourceHit:
    id: str
    at: str
    role: str
    preview: str


@dataclass(frozen=True)
class ImportResult:
    recognized: int
    added: int

    @property
    def duplicates(self) -> int:
        return self.recognized - self.added
