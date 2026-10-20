"""Единая иерархия ошибок.

Наследование от ValueError сохранено умышленно: прежний код поднимал
ValueError/RuntimeError, и внешние обработчики могли на это опираться.
"""
from __future__ import annotations


class WhoEngineError(Exception):
    """Базовая ошибка приложения."""


class ValidationError(WhoEngineError, ValueError):
    """Некорректные входные данные (группа, длина фрагмента, формат файла)."""


class ConfigurationError(WhoEngineError, ValueError):
    """Отсутствует или непригодна конфигурация (например, API-ключ)."""


class ArchiveFormatError(ValidationError):
    """Структура архива не распознана."""


class ProviderError(WhoEngineError, RuntimeError):
    """Сбой или несовместимость внешнего провайдера модели."""
