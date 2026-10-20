"""Раздел «Проверка API»: связь, ключ, доступные модели."""
from __future__ import annotations

import streamlit as st

from ..domain import ModelInfo
from ..services import DiagnosticsService
from .session import SessionStore

INTRO = ('Проверка ключа и перечень моделей выполняются бесплатно: токены не '
         'расходуются. Тестовый запрос внизу — платный, как и любой другой '
         'запрос к модели.')
NO_KEY_HINT = ('Ключ не задан. Укажите его в боковой панели или в .env, '
               'затем вернитесь сюда.')


class DiagnosticsPage:
    label = 'Проверка API'

    def __init__(self, service: DiagnosticsService, store: SessionStore,
                 key_present: bool) -> None:
        self._service = service
        self._store = store
        self._key_present = key_present

    def render(self) -> None:
        st.subheader('Проверка связи с xAI')
        st.caption(INTRO)
        if not self._key_present:
            st.warning(NO_KEY_HINT)
            return
        self._key_section()
        st.divider()
        self._models_section()
        st.divider()
        self._probe_section()

    # --- бесплатные проверки ------------------------------------------------

    def _key_section(self) -> None:
        st.markdown('**1. Ключ** — бесплатно')
        if not st.button('Проверить ключ'):
            return
        try:
            with st.spinner('Запрашиваем сведения о ключе…'):
                info = self._service.check_key()
        except Exception as exc:
            st.error(f'Ключ не прошёл проверку: {exc}')
            return
        if info.usable:
            st.success('Ключ принят и активен.')
        else:
            st.error('Ключ принят, но заблокирован или отключён.')
        st.write({
            'ключ': info.redacted or '—',
            'название': info.name or '—',
            'заблокирован': info.blocked,
            'отключён': info.disabled,
            'права': ', '.join(info.acls) or '—',
        })

    def _models_section(self) -> None:
        st.markdown('**2. Доступные модели** — бесплатно')
        st.caption('Список подставляется в выбор модели в боковой панели.')
        if st.button('Загрузить список моделей'):
            try:
                with st.spinner('Запрашиваем список моделей…'):
                    models = self._service.models()
            except Exception as exc:
                st.error(f'Не удалось получить список: {exc}')
                return
            self._store.set_catalog(models)
            # Боковая панель отрисовывается раньше тела страницы, поэтому
            # без перезапуска новый список попал бы в выбор модели только
            # со следующего действия пользователя.
            st.rerun()
        catalog = self._store.catalog()
        if catalog:
            st.success(f'Доступно моделей: {len(catalog)}. '
                       'Список подставлен в боковую панель.')
            st.dataframe(
                [self._model_row(model) for model in catalog],
                use_container_width=True, hide_index=True)

    @staticmethod
    def _model_row(model: ModelInfo) -> dict:
        return {
            'Модель': model.name,
            'Версия': model.version or '—',
            'Контекст': model.max_prompt_length or '—',
            'Псевдонимы': ', '.join(model.aliases) or '—',
        }

    # --- платная проверка ---------------------------------------------------

    def _probe_section(self) -> None:
        model = self._store.model()
        st.markdown('**3. Тестовый запрос** — платный')
        st.caption(f'Отправляет одно сообщение «{self._service.PROBE_PROMPT}» '
                   f'модели {model}. Подтверждает, что доступ к самой модели есть.')
        confirmed = st.checkbox(
            'Подтверждаю один платный тестовый запрос', value=False)
        if not st.button('Отправить тестовый запрос', disabled=not confirmed):
            return
        try:
            with st.spinner('Ждём xAI…'):
                result = self._service.probe(model)
        except Exception as exc:
            st.error(f'Запрос не прошёл: {exc}')
            return
        st.success(f'Ответ получен от модели {result.model}.')
        st.write({'ответ': result.answer, 'request_id': result.request_id or '—'})
        if result.usage:
            st.write(result.usage)
