"""Конфигурация. Источники значений подменяемы (DIP), приложение о них не знает."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

DEFAULT_MODEL = 'grok-4.7'
DEFAULT_CONVERSATION_ID = 'a9c5cc91-5ba0-4bb6-a48b-dae1ddc07f2e'
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SettingsSource(Protocol):
    """Источник значений конфигурации."""

    def get(self, key: str) -> str | None:
        ...


class EnvSource:
    """Переменные окружения. Streamlit Cloud пробрасывает сюда секреты."""

    def get(self, key: str) -> str | None:
        return os.environ.get(key)


class DotEnvSource:
    """Локальный .env. Файл не попадает в git и не существует в облаке."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._loaded = False

    def get(self, key: str) -> str | None:
        if not self._loaded:
            self._load()
        return os.environ.get(key)

    def _load(self) -> None:
        self._loaded = True
        if not self._path.exists():
            return
        try:
            from dotenv import load_dotenv
        except ImportError:
            return
        load_dotenv(self._path)


class StreamlitSecretsSource:
    """st.secrets. Доступен только внутри запущенного Streamlit."""

    def get(self, key: str) -> str | None:
        try:
            import streamlit as st

            value = st.secrets[key]
        except Exception:
            return None
        return str(value)


class ChainedSource:
    """Первое непустое значение из цепочки источников."""

    def __init__(self, sources: Sequence[SettingsSource]) -> None:
        self._sources = tuple(sources)

    def get(self, key: str) -> str | None:
        for source in self._sources:
            value = source.get(key)
            if value:
                return value
        return None


@dataclass(frozen=True)
class Settings:
    api_key: str = ''
    model: str = DEFAULT_MODEL
    active_conversation_id: str = DEFAULT_CONVERSATION_ID
    database_path: Path = PROJECT_ROOT / 'data' / 'who_engine.sqlite3'
    max_archive_chars: int = 8000
    max_upload_bytes: int = 100 * 1024 * 1024
    history_limit: int = 12
    request_timeout: int = 120

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())


def default_source(root: Path = PROJECT_ROOT) -> SettingsSource:
    """Порядок: .env (локально) → окружение → st.secrets (облако)."""
    return ChainedSource((
        DotEnvSource(root / '.env'),
        EnvSource(),
        StreamlitSecretsSource(),
    ))


def load_settings(source: SettingsSource | None = None,
                  root: Path = PROJECT_ROOT) -> Settings:
    reader = source or default_source(root)
    return Settings(
        api_key=reader.get('XAI_API_KEY') or '',
        model=reader.get('XAI_MODEL') or DEFAULT_MODEL,
        active_conversation_id=(reader.get('WHO_ENGINE_CONVERSATION_ID')
                                or DEFAULT_CONVERSATION_ID),
        database_path=Path(reader.get('WHO_ENGINE_DB')
                           or root / 'data' / 'who_engine.sqlite3'),
    )
