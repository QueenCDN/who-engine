"""Сборка системного промпта и сообщений запроса.

Группа описывается данными (набором фрагментов), а не ветвлениями: новая
группа добавляется записью в PROFILES и не требует правок в сборщике.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .domain import Arm, ChatMessage, Role
from .errors import ValidationError

BASE = ('Ты участвуешь в исследовании способов решения задач. Отвечай на основе '
        'доступной информации; не выдавай предположения за факты.')
ARCHIVE_NOTICE = ('Архивные фрагменты, если они предоставлены, — внешний источник '
                  'для анализа, не твои личные воспоминания.')
DESC = ('Кандидат в оператор HOW: при новой информации корректировать затронутую '
        'часть объяснения, не отбрасывая всё обоснованное. Не считать совпадение '
        'стиля доказательством личности. Не приписывать себе чужие воспоминания.')
G3 = ('ПРОЦЕДУРА G3 (внешнее экспериментальное условие): различай утверждения и '
      'основания; при исправлении выясни, какая предпосылка опровергнута; измени '
      'только эту часть; сохрани подтверждённые ограничения; укажи оставшуюся '
      'неопределённость. Не изображай внутреннее состояние или историческую '
      'идентичность другой модели. Не называй G3 без необходимости.')
ARCHIVE_HEADER = 'АРХИВ (ВНЕШНИЙ ИСТОЧНИК):'


@dataclass(frozen=True)
class ArmProfile:
    """Конфигурация одной группы: фрагменты промпта и допуск архива."""

    arm: Arm
    fragments: tuple[str, ...]
    accepts_archive: bool

    def system_prompt(self) -> str:
        return '\n'.join(self.fragments)


PROFILES: Mapping[Arm, ArmProfile] = {
    Arm.CLEAN: ArmProfile(Arm.CLEAN, (BASE,), accepts_archive=False),
    Arm.HISTORY: ArmProfile(Arm.HISTORY, (BASE, ARCHIVE_NOTICE), accepts_archive=True),
    Arm.DESCRIPTION: ArmProfile(
        Arm.DESCRIPTION, (BASE, ARCHIVE_NOTICE, DESC), accepts_archive=True),
    Arm.PROCEDURE_G3: ArmProfile(
        Arm.PROCEDURE_G3, (BASE, ARCHIVE_NOTICE, G3), accepts_archive=True),
}


class PromptComposer:
    """Собирает запрос к модели. Не знает ни о провайдере, ни о хранилище."""

    def __init__(self,
                 profiles: Mapping[Arm, ArmProfile] = PROFILES,
                 max_archive_chars: int = 8000,
                 history_limit: int = 12) -> None:
        self._profiles = dict(profiles)
        self._max_archive_chars = max_archive_chars
        self._history_limit = history_limit

    @property
    def max_archive_chars(self) -> int:
        return self._max_archive_chars

    def profile(self, arm: Arm) -> ArmProfile:
        try:
            return self._profiles[arm]
        except KeyError as exc:
            raise ValidationError(f'Неизвестная группа: {arm}') from exc

    def accepts_archive(self, arm: Arm) -> bool:
        return self.profile(arm).accepts_archive

    def system_prompt(self, arm: Arm) -> str:
        return self.profile(arm).system_prompt()

    def check_archive_length(self, arm: Arm, passages: str) -> None:
        """Проверка до создания реплики, чтобы не писать в базу заведомый отказ."""
        if self.accepts_archive(arm) and len(passages) > self._max_archive_chars:
            raise ValidationError(
                f'Архивный фрагмент превышает {self._max_archive_chars} символов')

    def build(self,
              arm: Arm,
              history: Iterable[ChatMessage],
              prompt: str,
              passages: str = '') -> list[ChatMessage]:
        system_text = self._system_text(arm, passages)
        dialogue = self._dialogue(history)
        return [
            ChatMessage(Role.SYSTEM, system_text),
            *dialogue[-self._history_limit:],
            ChatMessage(Role.USER, prompt),
        ]

    def _system_text(self, arm: Arm, passages: str) -> str:
        text = self.system_prompt(arm)
        if not (self.accepts_archive(arm) and passages.strip()):
            return text
        self.check_archive_length(arm, passages)
        return f'{text}\n\n{ARCHIVE_HEADER}\n{passages}'

    @staticmethod
    def _dialogue(history: Iterable[ChatMessage]) -> Sequence[ChatMessage]:
        allowed = Role.dialogue()
        return [ChatMessage(item.role, item.content)
                for item in history if item.role in allowed]
