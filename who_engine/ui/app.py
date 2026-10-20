"""Корень композиции: здесь и только здесь собираются зависимости."""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ..archive import default_importer
from ..config import Settings, load_settings
from ..prompts import PromptComposer
from ..providers import ChatClient, NullChatClient, XaiChatClient
from ..services import (ArchiveService, BackupService, ExperimentService,
                        ObservationService)
from ..storage import SqliteRepository
from .archive import ArchivePage
from .backup import BackupPage
from .base import PageRouter
from .experiments import ExperimentsPage
from .observations import ObservationsPage

TITLE = 'WHO-ENGINE v0.2'
DISCLAIMER = ('Локальный исследовательский инструмент. Не доказывает и не '
              'переносит WHO исходной модели.')
MODEL_HELP = ('Используйте доступный вам ID модели; он должен быть одинаковым '
              'в сравниваемых группах.')
COST_WARNING = 'API-запросы могут быть платными. Автоповторов нет.'


def chat_client(settings: Settings) -> ChatClient:
    """Без ключа подставляется офлайн-клиент, а не отключается половина UI."""
    if not settings.has_api_key:
        return NullChatClient()
    return XaiChatClient(settings.api_key, timeout=settings.request_timeout)


@dataclass
class App:
    """Приложение: знает о сервисах, но не о том, как они реализованы."""

    settings: Settings
    repository: SqliteRepository
    client: ChatClient
    composer: PromptComposer

    def run(self) -> None:
        st.set_page_config(page_title=TITLE, page_icon='🧭', layout='wide')
        self.repository.init()
        st.title(TITLE)
        st.caption(DISCLAIMER)
        with st.sidebar:
            model = self._settings_panel()
            router = self._router(model)
            selected = st.radio('Раздел', router.labels)
        router.render(selected)

    def _settings_panel(self) -> str:
        st.header('Настройки')
        status = ('настроен' if self.settings.has_api_key
                  else 'не настроен (офлайн режим)')
        st.write('API ключ:', status)
        model = st.text_input('Модель xAI', value=self.settings.model,
                              help=MODEL_HELP)
        st.warning(COST_WARNING)
        return model

    def _router(self, model: str) -> PageRouter:
        experiments = ExperimentService(
            runs=self.repository, turns=self.repository,
            client=self.client, composer=self.composer)
        observations = ObservationService(
            notes=self.repository, export=self.repository)
        archive = ArchiveService(
            source=self.repository,
            importer=default_importer(self.settings.max_upload_bytes),
            conversation_id=self.settings.active_conversation_id)
        return PageRouter((
            ExperimentsPage(experiments, model, self.settings.has_api_key),
            ArchivePage(archive),
            ObservationsPage(experiments, observations),
            BackupPage(BackupService(self.repository)),
        ))


def build_app(settings: Settings | None = None) -> App:
    resolved = settings or load_settings()
    return App(
        settings=resolved,
        repository=SqliteRepository(resolved.database_path),
        client=chat_client(resolved),
        composer=PromptComposer(
            max_archive_chars=resolved.max_archive_chars,
            history_limit=resolved.history_limit),
    )


def main() -> None:
    build_app().run()
