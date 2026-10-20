"""Хранилище: дедупликация импорта, статусы реплик, экспорт."""
import json
import tempfile
import unittest
from pathlib import Path

from who_engine.domain import Arm, ArchiveRecord, Role, TurnStatus
from who_engine.storage import SqliteRepository


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.repo = SqliteRepository(Path(self._dir.name) / 'test.sqlite3')
        self.repo.init()

    def tearDown(self):
        self._dir.cleanup()

    def test_run_roundtrip(self):
        run_id = self.repo.create_run('Проверка', Arm.PROCEDURE_G3.label, 'grok')
        runs = self.repo.list_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].id, run_id)
        self.assertIs(runs[0].arm, Arm.PROCEDURE_G3)

    def test_turn_status_update(self):
        run_id = self.repo.create_run('t', Arm.CLEAN.label, 'grok')
        turn_id = self.repo.add_turn(run_id, Role.USER, 'вопрос',
                                     TurnStatus.INFLIGHT)
        self.repo.update_turn(turn_id, TurnStatus.UNCERTAIN, error='таймаут')
        turn = self.repo.list_turns(run_id)[0]
        self.assertIs(turn.status, TurnStatus.UNCERTAIN)
        self.assertEqual(turn.error, 'таймаут')
        self.assertFalse(turn.is_complete)

    def test_import_deduplicates(self):
        rows = [ArchiveRecord('id1', 'c1', 'at', 'user', 'текст')]
        self.assertEqual(self.repo.save_records(rows), 1)
        self.assertEqual(self.repo.save_records(rows), 0)
        self.assertEqual(self.repo.count('c1'), 1)

    def test_search_requires_query(self):
        self.repo.save_records([ArchiveRecord('id1', 'c1', 'at', 'user', 'ключ')])
        self.assertEqual(self.repo.search('c1', '   '), [])
        self.assertEqual(len(self.repo.search('c1', 'клю')), 1)

    def test_summaries_are_scoped_to_conversation(self):
        self.repo.save_records([
            ArchiveRecord('a', 'c1', '2026-01-01', 'user', 'x'),
            ArchiveRecord('b', 'c1', '2026-01-02', 'assistant', 'y'),
            ArchiveRecord('c', 'c2', '2026-01-03', 'user', 'z'),
        ])
        summaries = self.repo.summaries('c1')
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].message_count, 2)
        self.assertEqual(summaries[0].latest, '2026-01-02')

    def test_export_is_json(self):
        run_id = self.repo.create_run('t', Arm.CLEAN.label, 'grok')
        self.repo.add_turn(run_id, Role.USER, 'вопрос', TurnStatus.COMPLETE)
        self.repo.add_note(run_id, 'G3', 'наблюдение', 'интерпретация', 'низкая')
        payload = json.loads(self.repo.export_run(run_id))
        self.assertEqual(len(payload['turns']), 1)
        self.assertEqual(len(payload['notes']), 1)

    def test_backup_creates_file(self):
        self.repo.create_run('t', Arm.CLEAN.label, 'grok')
        target = self.repo.backup()
        self.assertTrue(target.exists())
        self.assertGreater(target.stat().st_size, 0)


if __name__ == '__main__':
    unittest.main()
