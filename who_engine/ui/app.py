"""Корень композиции: здесь и только здесь собираются зависимости."""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ..archive import default_importer
from ..config import Settings, load_settings
from ..prompts import PromptComposer
from ..providers import Provider, build_provider
from ..services import (ArchiveService, BackupService, DiagnosticsService,
                        ExperimentService, ObservationService)
from ..storage import SqliteRepository
from .archive import ArchivePage
from .backup import BackupPage
from .base import PageRouter
from .diagnostics import DiagnosticsPage
from .experiments import ExperimentsPage
from .observations import ObservationsPage
from .session import FROM_UI, SessionStore

TITLE = 'WHO-ENGINE v0.2'
DISCLAIMER = ('Локальный исследовательский инструмент. Не доказывает и не '
              'переносит WHO исходной модели.')
KEY_HELP = ('Хранится только в памяти этой сессии: на диск не пишется и в '
            'репозиторий не попадает. Пусто — берётся ключ из .env или секретов.')
MODEL_HELP = ('Модель должна быть одинаковой в сравниваемых группах. Полный '
              'список загружается в разделе «Проверка API».')
COST_WARNING = 'API-запросы могут быть платными. Автоповторов нет.'
OTHER_MODEL = 'Другая модель…'


@dataclass
class App:
    """Приложение: знает о сервисах, но не о том, как они реализованы."""

    settings: Settings
    repository: SqliteRepository
    composer: PromptComposer

    def run(self) -> None:
        st.set_page_config(page_title=TITLE, page_icon='🧭', layout='wide')
        self.repository.init()
        store = SessionStore(st.session_state, self.settings)
        st.title(TITLE)
        st.caption(DISCLAIMER)
        with st.sidebar:
            credentials = self._key_panel(store)
            provider = build_provider(credentials.api_key,
                                      timeout=self.settings.request_timeout)
            model = self._model_panel(store)
            st.warning(COST_WARNING)
            router = self._router(provider, store, model, credentials.present)
            selected = st.radio('Раздел', router.labels)
        router.render(selected)

    # --- боковая панель -----------------------------------------------------

    def _key_panel(self, store: SessionStore):
        st.header('Настройки')
        entered = st.text_input('API ключ xAI', value='', type='password',
                                help=KEY_HELP,
                                placeholder='xai-…')
        if entered:
            store.set_api_key(entered)
        credentials = store.credentials()
        st.caption(f'Ключ: {credentials.source}')
        if credentials.source == FROM_UI and st.button('Сбросить введённый ключ'):
            store.clear_api_key()
            st.rerun()
        return credentials

    def _model_panel(self, store: SessionStore) -> str:
        options = store.model_options()
        current = store.model()
        choices = [*options, OTHER_MODEL]
        index = options.index(current) if current in options else 0
        chosen = st.selectbox('Модель xAI', choices, index=index,
                              help=MODEL_HELP)
        if chosen == OTHER_MODEL:
            chosen = st.text_input('ID модели вручную', value=current)
        store.set_model(chosen)
        return store.model()

    # --- сборка разделов ----------------------------------------------------

    def _router(self, provider: Provider, store: SessionStore, model: str,
                key_present: bool) -> PageRouter:
        experiments = ExperimentService(
            runs=self.repository, turns=self.repository,
            client=provider, composer=self.composer)
        observations = ObservationService(
            notes=self.repository, export=self.repository)
        archive = ArchiveService(
            source=self.repository,
            importer=default_importer(self.settings.max_upload_bytes),
            conversation_id=self.settings.active_conversation_id)
        diagnostics = DiagnosticsService(
            inspector=provider, catalog=provider, chat=provider)
        return PageRouter((
            ExperimentsPage(experiments, model, key_present),
            ArchivePage(archive),
            ObservationsPage(experiments, observations),
            DiagnosticsPage(diagnostics, store, key_present),
            BackupPage(BackupService(self.repository)),
        ))


def build_app(settings: Settings | None = None) -> App:
    resolved = settings or load_settings()
    return App(
        settings=resolved,
        repository=SqliteRepository(resolved.database_path),
        composer=PromptComposer(
            max_archive_chars=resolved.max_archive_chars,
            history_limit=resolved.history_limit),
    )


def main() -> None:
    build_app().run()
