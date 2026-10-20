"""Состояние сессии: ключ и выбранная модель.

Ключ, введённый в интерфейсе, живёт только в памяти сессии Streamlit:
на диск он не пишется и в репозиторий попасть не может.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import MutableMapping

from ..config import Settings
from ..domain import ModelInfo

KEY_FIELD = 'api_key_override'
MODEL_FIELD = 'selected_model'
MODELS_FIELD = 'model_catalog'

FROM_UI = 'введён в интерфейсе'
FROM_ENV = 'из .env или секретов'
MISSING = 'не задан (офлайн режим)'


@dataclass(frozen=True)
class Credentials:
    api_key: str
    source: str

    @property
    def present(self) -> bool:
        return bool(self.api_key.strip())


class SessionStore:
    """Доступ к состоянию сессии без прямых обращений к st.session_state."""

    def __init__(self, state: MutableMapping, settings: Settings) -> None:
        self._state = state
        self._settings = settings

    # --- ключ ---------------------------------------------------------------

    def override(self) -> str:
        """Ключ, введённый в интерфейсе, без обращения к .env."""
        return str(self._state.get(KEY_FIELD, '') or '').strip()

    def credentials(self) -> Credentials:
        """Приоритет: введённый в интерфейсе ключ, затем .env/секреты."""
        override = self.override()
        if override:
            return Credentials(override, FROM_UI)
        if self._settings.has_api_key:
            return Credentials(self._settings.api_key, FROM_ENV)
        return Credentials('', MISSING)

    def set_api_key(self, value: str) -> None:
        self._state[KEY_FIELD] = value.strip()

    def clear_api_key(self) -> None:
        self._state.pop(KEY_FIELD, None)

    # --- модель -------------------------------------------------------------

    def model(self) -> str:
        return str(self._state.get(MODEL_FIELD) or self._settings.model)

    def set_model(self, value: str) -> None:
        cleaned = value.strip()
        if cleaned:
            self._state[MODEL_FIELD] = cleaned

    # --- каталог моделей ----------------------------------------------------

    def catalog(self) -> list[ModelInfo]:
        return list(self._state.get(MODELS_FIELD) or [])

    def set_catalog(self, models: list[ModelInfo]) -> None:
        self._state[MODELS_FIELD] = list(models)

    def model_options(self) -> list[str]:
        """Загруженные модели плюс текущая и настроенная — без повторов."""
        names = [model.name for model in self.catalog()]
        for extra in (self.model(), self._settings.model):
            if extra and extra not in names:
                names.append(extra)
        return names
