"""Раздел «Эксперименты»."""
from __future__ import annotations

import streamlit as st

from ..domain import Arm, Run, Turn
from ..errors import ValidationError
from ..services import ExperimentService, UncertainRequest

PROTOCOL_HINT = ('A: нет архива/оператора; B: архив; C: тот же архив + описание '
                 'HOW; D: тот же архив + процедура G3. Исторические фрагменты '
                 'подаются вручную и должны совпадать в B/C/D для сравнения.')
RIGOUR_HINT = ('Для строгого A/B/C/D: одна версия модели, одинаковая история '
               'активного диалога и один тестовый вопрос. Исторический фрагмент '
               'одинаков в B/C/D. Запуск отдельных экспериментов не гарантирует '
               'идентичность случайной генерации.')
UNCERTAIN_HINT = ('Статус uncertain: запрос мог дойти до сервера. Не повторяйте '
                  'автоматически. ')


class ExperimentsPage:
    label = 'Эксперименты'
    icon = ':material/science:'

    def __init__(self, service: ExperimentService, model: str,
                 api_key_present: bool) -> None:
        self._service = service
        self._model = model
        self._api_key_present = api_key_present

    def render(self) -> None:
        st.info(PROTOCOL_HINT)
        self._creation_form()
        runs = self._service.list_runs()
        if not runs:
            st.info('Создайте эксперимент')
            st.stop()
        run = self._select_run(runs)
        self._transcript(self._service.transcript(run.id))
        st.divider()
        self._composer(run)
        st.caption(RIGOUR_HINT)
        self._danger_zone(run)

    def _creation_form(self) -> None:
        with st.form('new'):
            title = st.text_input('Название эксперимента', 'Проверка G3')
            arm_label = st.selectbox('Группа', Arm.labels())
            st.caption(f'Модель нового эксперимента: {self._model}. '
                       'Изменить — в разделе «Проверка API».')
            if st.form_submit_button('Создать эксперимент'):
                self._service.create_run(
                    title, Arm.from_label(arm_label), self._model)
                st.rerun()

    @staticmethod
    def _select_run(runs: list[Run]) -> Run:
        return st.selectbox(
            'Эксперимент', runs,
            format_func=lambda run: f'{run.title} / {run.arm.label} / {run.short_id}')

    @staticmethod
    def _transcript(turns: list[Turn]) -> None:
        for turn in turns:
            with st.chat_message(turn.display_role.value):
                st.write(turn.content)
                if not turn.is_complete:
                    st.caption(f'{turn.status.value}: {turn.error or ""}')

    def _composer(self, run: Run) -> None:
        limit = self._service.composer.max_archive_chars
        passages = st.text_area(
            f'Архивный фрагмент (до {limit} символов; не применяется в A)',
            height=140)
        prompt = st.text_area('Следующее сообщение', height=110)
        confirmed = st.checkbox(
            'Подтверждаю платную отправку видимого текста в xAI API', value=False)
        ready = bool(prompt.strip()) and confirmed and self._api_key_present
        # Запрос уходит модели, записанной при создании эксперимента, а не
        # выбранной сейчас: иначе сравнение групп потеряло бы смысл.
        st.caption(f'Запрос уйдёт модели {run.model} — она закреплена за этим '
                   f'экспериментом.')
        if not self._api_key_present:
            st.info('Ключ не задан: отправка недоступна. '
                    'Укажите ключ в разделе «Проверка API».')
        if st.button('Отправить запрос', disabled=not ready):
            self._send(run, prompt, passages)

    def _send(self, run: Run, prompt: str, passages: str) -> None:
        try:
            self._service.validate_archive(run.arm, passages)
        except ValidationError as exc:
            st.error(str(exc))
            st.stop()
        try:
            with st.spinner('Ждём xAI…'):
                self._service.send(run, prompt, passages)
        except UncertainRequest as exc:
            st.error(UNCERTAIN_HINT + str(exc))
            return
        st.rerun()

    def _danger_zone(self, run: Run) -> None:
        """Удаление спрятано в свёрнутый блок и требует двух действий."""
        turns, notes = self._service.run_size(run.id)
        with st.expander('Удалить эксперимент'):
            st.warning(
                f'Будут безвозвратно удалены: эксперимент «{run.title}» '
                f'({run.arm.label}), реплик — {turns}, наблюдений — {notes}. '
                'Импортированный архив не затрагивается.')
            st.caption('Перед удалением журнал можно выгрузить в разделе '
                       '«Наблюдения и экспорт».')
            confirmed = st.checkbox(
                f'Подтверждаю удаление {run.short_id}', value=False,
                key=f'confirm_delete_{run.id}')
            if st.button('Удалить безвозвратно', disabled=not confirmed,
                         key=f'delete_{run.id}'):
                self._service.delete_run(run.id)
                st.rerun()
