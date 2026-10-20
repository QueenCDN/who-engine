"""Раздел «Резервное копирование»."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from ..services import BackupService

STATE_KEY = 'backup_path'


class BackupPage:
    label = 'Резервное копирование'
    icon = ':material/backup:'

    def __init__(self, service: BackupService) -> None:
        self._service = service

    def render(self) -> None:
        st.subheader('Резервная копия базы')
        if st.button('Создать резервную копию'):
            st.session_state[STATE_KEY] = str(self._service.create())
        self._offer_download()

    @staticmethod
    def _offer_download() -> None:
        stored = st.session_state.get(STATE_KEY)
        if not stored:
            return
        path = Path(stored)
        if not path.exists():
            return
        st.download_button('Скачать базу', path.read_bytes(),
                           file_name=path.name,
                           mime='application/octet-stream')
