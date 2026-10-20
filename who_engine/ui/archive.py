"""Раздел «Архив локально»."""
from __future__ import annotations

import streamlit as st

from ..domain import ConversationSummary
from ..services import ArchiveService

PREVIEW_LIMIT = 5
PREVIEW_CHARS = 400
FOOTER = ('Для неизвестного варианта JSON нужен анализ его структуры. Архив '
          'автоматически в API не уходит.')


class ArchivePage:
    label = 'Архив локально'
    icon = ':material/library_books:'

    def __init__(self, service: ArchiveService) -> None:
        self._service = service

    def render(self) -> None:
        st.subheader('Импорт архива без обращения к xAI API')
        self._import_form()
        st.write('Всего локально сохранённых сообщений: '
                 f'{self._service.total_messages()}')
        st.markdown('**Разговоры в локальной базе**')
        for summary in self._service.conversations():
            self._conversation(summary)
        self._search()
        st.caption(FOOTER)

    def _import_form(self) -> None:
        uploaded = st.file_uploader(
            'TXT после очистки или JSON из выгрузки Grok',
            type=list(self._service.supported_types))
        if uploaded is None or not st.button('Импортировать'):
            return
        try:
            result = self._service.import_file(uploaded.name, uploaded.getvalue())
        except Exception as exc:
            st.error(f'Не удалось импортировать: {exc}')
            return
        if not result.recognized:
            st.warning('Не удалось распознать сообщения. Исходник не изменён.')
            return
        st.success(f'Распознано: {result.recognized}; '
                   f'новых сообщений: {result.added}; '
                   f'дубликатов: {result.duplicates}.')

    def _conversation(self, summary: ConversationSummary) -> None:
        header = (f'{summary.conversation_id[:12]}… | '
                  f'{summary.message_count} сообщений | '
                  f'{summary.earliest or "?"} → {summary.latest or "?"}')
        with st.expander(header):
            st.caption('Превью начала разговора. Не отправляется в API.')
            messages = self._service.preview(
                summary.conversation_id, limit=PREVIEW_LIMIT)
            for message in messages:
                st.write(f'{message.at} — {message.role}: '
                         f'{message.text[:PREVIEW_CHARS]}')

    def _search(self) -> None:
        query = st.text_input('Локальный поиск по тексту')
        for hit in self._service.search(query):
            with st.expander(f'{hit.at} / {hit.role} / {hit.id[:10]}'):
                st.write(hit.preview)
