"""Раздел «Наблюдения и экспорт»."""
from __future__ import annotations

import streamlit as st

from ..domain import NOTE_LABELS, Confidence, Run
from ..services import ExperimentService, ObservationService


class ObservationsPage:
    label = 'Наблюдения и экспорт'
    icon = ':material/edit_note:'

    def __init__(self, experiments: ExperimentService,
                 observations: ObservationService) -> None:
        self._experiments = experiments
        self._observations = observations

    def render(self) -> None:
        runs = self._experiments.list_runs()
        if not runs:
            st.info('Создайте эксперимент')
            return
        run = st.selectbox(
            'Эксперимент', runs,
            format_func=lambda item: f'{item.title} / {item.short_id}')
        self._note_form(run)
        for note in self._observations.notes(run.id):
            st.write(note.as_tuple())
        st.download_button(
            'Скачать журнал JSON', self._observations.export(run.id),
            file_name=f'experiment_{run.short_id}.json',
            mime='application/json')

    def _note_form(self, run: Run) -> None:
        with st.form('note'):
            label = st.selectbox('Код', NOTE_LABELS)
            observation = st.text_area(
                'Наблюдение: что непосредственно сделала модель')
            interpretation = st.text_area(
                'Интерпретация: какой оператор это может объяснить')
            confidence = st.selectbox('Уверенность', Confidence.labels())
            if st.form_submit_button('Сохранить'):
                self._observations.add_note(
                    run.id, label, observation, interpretation, confidence)
                st.rerun()
