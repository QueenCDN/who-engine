"""Раздел «Проверка API»: ключ, модель, связь.

Здесь же живут настройки подключения — они нужны только в этом месте и не
загромождают навигацию.
"""
from __future__ import annotations

import streamlit as st

from ..domain import ModelInfo
from ..services import DiagnosticsService
from .session import FROM_UI, SessionStore

INTRO = ('Проверка ключа и перечень моделей выполняются бесплатно: токены не '
         'расходуются. Тестовый запрос внизу — платный, как и любой другой '
         'запрос к модели.')
KEY_HELP = ('Хранится только в памяти этой сессии: на диск не пишется и в '
            'репозиторий не попадает. Пусто — берётся ключ из .env или секретов.')
MODEL_HELP = ('Модель должна быть одинаковой в сравниваемых группах. Выбранная '
              'здесь модель используется для новых экспериментов.')
COST_WARNING = 'API-запросы могут быть платными. Автоповторов нет.'
NO_KEY_HINT = 'Без ключа доступна только настройка: запросы к xAI невозможны.'
OTHER_MODEL = 'Другая модель…'


class DiagnosticsPage:
    label = 'Проверка API'
    icon = ':material/network_check:'

    def __init__(self, service: DiagnosticsService, store: SessionStore,
                 key_present: bool) -> None:
        self._service = service
        self._store = store
        self._key_present = key_present

    def render(self) -> None:
        st.subheader('Подключение к xAI')
        st.caption(INTRO)
        st.warning(COST_WARNING)
        self._key_settings()
        st.divider()
        self._model_settings()
        st.divider()
        self._probe_section()

    # --- настройки подключения ----------------------------------------------

    def _key_settings(self) -> None:
        st.markdown('**Ключ xAI**')
        entered = st.text_input('API ключ', value=self._store.override(),
                                type='password', help=KEY_HELP,
                                placeholder='xai-…')
        if entered.strip() != self._store.override():
            self._store.set_api_key(entered)
            st.rerun()
        credentials = self._store.credentials()
        st.caption(f'Источник ключа: {credentials.source}')
        self._note_section_placement()
        if credentials.source == FROM_UI and st.button('Сбросить введённый ключ'):
            self._store.clear_api_key()
            st.rerun()
        if not self._key_present:
            st.info(NO_KEY_HINT)
            self._explain_missing_key()
            return
        self._key_check()

    @staticmethod
    def _note_section_placement() -> None:
        """Ключ читается и из секции, но на верхнем уровне он надёжнее."""
        from ..config import secret_section_holding

        section = secret_section_holding('XAI_API_KEY')
        if section:
            st.caption(f'Ключ найден внутри секции `[{section}]`. Он работает, '
                       'но на верхнем уровне Streamlit отдаёт его и в '
                       'переменные окружения — надёжнее перенести туда.')

    @staticmethod
    def _explain_missing_key() -> None:
        """Показывает ТОЛЬКО имена секретов — значения не читаются."""
        from ..config import env_var_present, secret_is_section, secret_names

        with st.expander('Почему ключ не виден?'):
            names = secret_names()
            if not names:
                st.write('Секреты приложения не заданы или не прочитаны. '
                         'Проверьте Settings → Secrets и перезапустите '
                         'приложение (⋮ → Reboot).')
            else:
                st.write('Видимые имена секретов (значения не показываются):')
                for name in names:
                    mark = ' — это секция, а не значение' if secret_is_section(name) else ''
                    st.write(f'• `{name}`{mark}')
            st.write(f'Переменная окружения `XAI_API_KEY`: '
                     f'{"задана" if env_var_present("XAI_API_KEY") else "нет"}')
            st.caption(
                'Ожидаются имена верхнего уровня `XAI_API_KEY` и `XAI_MODEL`. '
                'Если они оказались внутри секции — например, под `[general]` — '
                'Streamlit их не отдаёт по этим именам. Уберите заголовок секции '
                'и сохраните заново.')

    def _key_check(self) -> None:
        if not st.button('Проверить ключ', type='primary'):
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

    def _model_settings(self) -> None:
        st.markdown('**Модель**')
        options = self._store.model_options()
        current = self._store.model()
        choices = [*options, OTHER_MODEL]
        index = options.index(current) if current in options else 0
        chosen = st.selectbox('Модель xAI', choices, index=index, help=MODEL_HELP)
        if chosen == OTHER_MODEL:
            chosen = st.text_input('ID модели вручную', value=current)
        if chosen.strip() and chosen.strip() != current:
            self._store.set_model(chosen)
            st.rerun()
        if self._key_present:
            self._model_catalog()

    def _model_catalog(self) -> None:
        st.caption('Полный перечень можно загрузить из xAI — это бесплатно.')
        if st.button('Загрузить список моделей'):
            try:
                with st.spinner('Запрашиваем список моделей…'):
                    models = self._service.models()
            except Exception as exc:
                st.error(f'Не удалось получить список: {exc}')
                return
            self._store.set_catalog(models)
            st.rerun()
        catalog = self._store.catalog()
        if catalog:
            st.success(f'Доступно моделей: {len(catalog)}.')
            st.dataframe([self._model_row(model) for model in catalog],
                         width='stretch', hide_index=True)

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
        st.markdown('**Тестовый запрос — платный**')
        st.caption(f'Отправляет одно сообщение «{self._service.PROBE_PROMPT}» '
                   f'модели {model}. Подтверждает, что доступ к самой модели есть.')
        if not self._key_present:
            st.info(NO_KEY_HINT)
            return
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
