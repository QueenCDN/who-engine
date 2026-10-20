"""Сценарий отправки: один запрос, никаких автоповторов, статус uncertain."""
import tempfile
import unittest
from pathlib import Path

from who_engine.domain import Arm, ChatMessage, ChatReply, Role, TurnStatus
from who_engine.prompts import PromptComposer
from who_engine.services import ExperimentService, UncertainRequest
from who_engine.storage import SqliteRepository


class RecordingClient:
    """Подставной провайдер: считает вызовы и возвращает фиксированный ответ."""

    def __init__(self, reply=None, failure=None):
        self.calls: list[list[ChatMessage]] = []
        self._reply = reply or ChatReply('ответ', 'grok-test', {'tokens': 1}, 'req-1')
        self._failure = failure

    def complete(self, messages, model):
        self.calls.append(list(messages))
        if self._failure is not None:
            raise self._failure
        return self._reply


class SendTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.repo = SqliteRepository(Path(self._dir.name) / 'db.sqlite3')
        self.repo.init()

    def tearDown(self):
        self._dir.cleanup()

    def service(self, client):
        return ExperimentService(self.repo, self.repo, client, PromptComposer())

    def run_for(self, arm=Arm.PROCEDURE_G3):
        service = self.service(RecordingClient())
        run_id = service.create_run('t', arm, 'grok-test')
        return next(run for run in service.list_runs() if run.id == run_id)

    def test_successful_send_writes_both_turns(self):
        client = RecordingClient()
        service = self.service(client)
        run = self.run_for()
        service.send(run, 'вопрос', 'фрагмент')
        turns = service.transcript(run.id)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual([turn.role for turn in turns],
                         [Role.USER, Role.ASSISTANT])
        self.assertTrue(all(turn.is_complete for turn in turns))
        self.assertEqual(turns[1].content, 'ответ')
        self.assertEqual(turns[1].model, 'grok-test')

    def test_failure_leaves_uncertain_and_does_not_retry(self):
        client = RecordingClient(failure=TimeoutError('нет ответа'))
        service = self.service(client)
        run = self.run_for()
        with self.assertRaises(UncertainRequest):
            service.send(run, 'вопрос')
        turns = service.transcript(run.id)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(turns), 1)
        self.assertIs(turns[0].status, TurnStatus.UNCERTAIN)
        self.assertIn('нет ответа', turns[0].error)

    def test_uncertain_turn_is_excluded_from_next_history(self):
        failing = self.service(RecordingClient(failure=TimeoutError('x')))
        run = self.run_for()
        with self.assertRaises(UncertainRequest):
            failing.send(run, 'потерянный вопрос')
        client = RecordingClient()
        self.service(client).send(run, 'новый вопрос')
        sent = [message.content for message in client.calls[0]]
        self.assertNotIn('потерянный вопрос', sent)
        self.assertEqual(sent[-1], 'новый вопрос')

    def test_clean_arm_ignores_archive(self):
        client = RecordingClient()
        service = self.service(client)
        run = self.run_for(Arm.CLEAN)
        service.send(run, 'вопрос', 'секретный фрагмент')
        self.assertNotIn('секретный фрагмент', client.calls[0][0].content)


if __name__ == '__main__':
    unittest.main()
