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
from .navigation import SidebarNavigation
from .observations import ObservationsPage
from .session import SessionStore

TITLE = 'WHO-ENGINE v0.2'
DISCLAIMER = ('Локальный исследовательский инструмент. Не доказывает и не '
              'переносит WHO исходной модели.')


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
        # Ключ и модель читаются из состояния сессии, а не из виджетов боковой
        # панели: настройки живут в разделе «Проверка API», который
        # отрисовывается уже после того, как провайдер собран.
        credentials = store.credentials()
        provider = build_provider(credentials.api_key,
                                  timeout=self.settings.request_timeout)
        st.title(TITLE)
        st.caption(DISCLAIMER)
        router = self._router(provider, store, store.model(),
                              credentials.present)
        with st.sidebar:
            st.header('Разделы')
            selected = SidebarNavigation(router, st.session_state).render()
        router.render(selected)

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
