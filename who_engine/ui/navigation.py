"""Навигация по разделам кнопками.

Выбор раздела хранится в состоянии сессии, а не в значении виджета:
маршрутизация не зависит от того, чем именно её отрисовали.
"""
from __future__ import annotations

from typing import MutableMapping

import streamlit as st

from .base import PageRouter

ACTIVE_FIELD = 'active_page'

# Streamlit центрирует содержимое кнопки целиком, поэтому значки съезжают
# вслед за длиной подписи. Параметра выравнивания у st.button нет, так что
# прижимаем содержимое влево стилем. Селекторы — по data-testid: классы
# st-emotion-cache-* меняются от сборки к сборке.
NAV_STYLE = '''
<style>
[data-testid="stSidebar"] [data-testid="stButton"] button {
    justify-content: flex-start;
    padding-left: 0.85rem;
}
[data-testid="stSidebar"] [data-testid="stButton"] button > div {
    justify-content: flex-start;
    width: 100%;
}
</style>
'''


class SidebarNavigation:
    """Кнопка на раздел; активный выделен основным стилем."""

    def __init__(self, router: PageRouter, state: MutableMapping) -> None:
        self._router = router
        self._state = state

    @property
    def current(self) -> str:
        label = self._state.get(ACTIVE_FIELD)
        return label if label in self._router.labels else self._router.default

    def render(self) -> str:
        st.markdown(NAV_STYLE, unsafe_allow_html=True)
        current = self.current
        for label in self._router.labels:
            selected = label == current
            if st.button(label, key=f'nav_{label}', width='stretch',
                         icon=self._router.icon(label),
                         type='primary' if selected else 'secondary'):
                self._state[ACTIVE_FIELD] = label
                # Перезапуск, чтобы подсветка и содержимое страницы
                # обновились одновременно, а не через одно действие.
                st.rerun()
        return current
