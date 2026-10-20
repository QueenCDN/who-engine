"""Удаление эксперимента и проверка связи с API."""
import tempfile
import unittest
from pathlib import Path

from who_engine.domain import (ApiKeyInfo, Arm, ChatReply, ModelInfo, Role,
                               TurnStatus)
from who_engine.prompts import PromptComposer
from who_engine.providers import NullProvider, build_provider
from who_engine.errors import ConfigurationError
from who_engine.services import DiagnosticsService, ExperimentService
from who_engine.storage import SqliteRepository


class FakeProvider:
    """Подставной провайдер: считает вызовы каждого вида."""

    available = True

    def __init__(self):
        self.chat_calls = 0
        self.key_calls = 0
        self.model_calls = 0

    def complete(self, messages, model):
        self.chat_calls += 1
        return ChatReply('связь', model, {'tokens': 2}, 'req-7')

    def key_info(self):
        self.key_calls += 1
        return ApiKeyInfo(redacted='xai-***abc', name='research',
                          acls=('chat',))

    def language_models(self):
        self.model_calls += 1
        return [ModelInfo('grok-4.7', version='1'), ModelInfo('grok-3')]


class DeleteRunTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.repo = SqliteRepository(Path(self._dir.name) / 'db.sqlite3')
        self.repo.init()
        self.service = ExperimentService(
            self.repo, self.repo, FakeProvider(), PromptComposer())

    def tearDown(self):
        self._dir.cleanup()

    def _run_with_content(self):
        run_id = self.service.create_run('Проверка', Arm.CLEAN, 'grok')
        self.repo.add_turn(run_id, Role.USER, 'вопрос', TurnStatus.COMPLETE)
        self.repo.add_turn(run_id, Role.ASSISTANT, 'ответ', TurnStatus.COMPLETE)
        self.repo.add_note(run_id, 'G3', 'набл', 'интерпр', 'низкая')
        return run_id

    def test_run_size_counts_turns_and_notes(self):
        run_id = self._run_with_content()
        self.assertEqual(self.service.run_size(run_id), (2, 1))

    def test_delete_removes_everything(self):
        run_id = self._run_with_content()
        self.service.delete_run(run_id)
        self.assertEqual(self.service.list_runs(), [])
        self.assertEqual(self.repo.list_turns(run_id), [])
        self.assertEqual(self.repo.list_notes(run_id), [])

    def test_delete_keeps_other_runs(self):
        kept = self._run_with_content()
        doomed = self._run_with_content()
        self.service.delete_run(doomed)
        self.assertEqual([run.id for run in self.service.list_runs()], [kept])
        self.assertEqual(self.service.run_size(kept), (2, 1))

    def test_delete_keeps_imported_archive(self):
        from who_engine.domain import ArchiveRecord
        self.repo.save_records([ArchiveRecord('a', 'c1', 'at', 'user', 'текст')])
        self.service.delete_run(self._run_with_content())
        self.assertEqual(self.repo.count('c1'), 1)


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider()
        self.service = DiagnosticsService(
            self.provider, self.provider, self.provider)

    def test_key_check_is_free(self):
        info = self.service.check_key()
        self.assertTrue(info.usable)
        self.assertEqual(self.provider.key_calls, 1)
        self.assertEqual(self.provider.chat_calls, 0)

    def test_model_list_is_free(self):
        models = self.service.models()
        self.assertEqual([m.name for m in models], ['grok-4.7', 'grok-3'])
        self.assertEqual(self.provider.chat_calls, 0)

    def test_probe_sends_exactly_one_request(self):
        result = self.service.probe('grok-4.7')
        self.assertEqual(self.provider.chat_calls, 1)
        self.assertEqual(result.answer, 'связь')
        self.assertEqual(result.request_id, 'req-7')

    def test_blocked_key_is_not_usable(self):
        self.assertFalse(ApiKeyInfo(redacted='x', blocked=True).usable)
        self.assertFalse(ApiKeyInfo(redacted='x', disabled=True).usable)


class ProviderFactoryTests(unittest.TestCase):
    def test_empty_key_gives_offline_provider(self):
        provider = build_provider('   ')
        self.assertIsInstance(provider, NullProvider)
        self.assertFalse(provider.available)
        for call in (lambda: provider.key_info(),
                     lambda: provider.language_models()):
            with self.assertRaises(ConfigurationError):
                call()

    def test_key_gives_live_provider(self):
        self.assertTrue(build_provider('xai-test').available)


if __name__ == '__main__':
    unittest.main()
