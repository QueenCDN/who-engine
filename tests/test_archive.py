"""Разбор архивов: распознавание, дедупликация, отказ при неизвестной схеме."""
import unittest

from who_engine.archive import GrokJsonParser, GrokTxtParser, default_importer
from who_engine.archive.json_export import XaiMetadataParser, normalize_role
from who_engine.errors import ArchiveFormatError, ValidationError

TXT = ('## 00001\nrole: user\ndatetime: 2026-01-01\nconversation_id: abc\n\nПривет\n'
       '## 00002\nrole: assistant\ndatetime: 2026-01-02\nconversation_id: abc\n\nОтвет')


class TxtTests(unittest.TestCase):
    def setUp(self):
        self.parser = GrokTxtParser()

    def test_two_messages(self):
        rows = self.parser.parse(TXT)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].text, 'Привет')
        self.assertEqual(rows[1].text, 'Ответ')
        self.assertEqual(rows[0].conversation_id, 'abc')

    def test_identity_is_stable(self):
        self.assertEqual([r.id for r in self.parser.parse(TXT)],
                         [r.id for r in self.parser.parse(TXT)])

    def test_identity_follows_content(self):
        changed = TXT.replace('Привет', 'Привет!')
        self.assertNotEqual(self.parser.parse(TXT)[0].id,
                            self.parser.parse(changed)[0].id)


class JsonTests(unittest.TestCase):
    def setUp(self):
        self.parser = GrokJsonParser()

    def test_flat_shape(self):
        raw = '[{"id":"abc","messages":[{"role":"user","created_at":"y","content":"z"}]}]'
        rows = self.parser.parse(raw)
        self.assertEqual(rows[0].text, 'z')
        self.assertEqual(rows[0].conversation_id, 'abc')
        self.assertEqual(rows[0].at, 'y')

    def test_xai_shape_with_mongo_date(self):
        raw = ('{"conversations":[{"conversation":{"id":"c1"},"responses":[{"response":'
               '{"_id":"r1","sender":"human","create_time":{"$date":'
               '{"$numberLong":"1700000000000"}},"content":"вопрос"}}]}]}')
        rows = self.parser.parse(raw)
        self.assertEqual(rows[0].role, 'user')
        self.assertEqual(rows[0].conversation_id, 'c1')
        self.assertTrue(rows[0].at.startswith('2023-11-'))

    def test_role_aliases(self):
        self.assertEqual(normalize_role('ASSISTANT'), 'assistant')
        self.assertEqual(normalize_role('grok'), 'assistant')
        self.assertEqual(normalize_role({'role': 'human'}), 'user')
        self.assertIsNone(normalize_role('system'))

    def test_unknown_structure_fails_closed(self):
        with self.assertRaises(ArchiveFormatError):
            self.parser.parse('{"что-то":1}')

    def test_no_messages_recognized(self):
        with self.assertRaises(ArchiveFormatError):
            self.parser.parse('[{"id":"abc","messages":[]}]')

    def test_metadata(self):
        raw = ('{"conversations":[{"conversation":{"id":"c1"},"responses":[{"response":'
               '{"_id":"r1","parent_response_id":"r0","model":"grok","path":[1,2]}}]}]}')
        items = XaiMetadataParser().parse(raw)
        self.assertEqual(items[0].raw_id, 'r1')
        self.assertEqual(items[0].parent_id, 'r0')
        self.assertEqual(items[0].path_json, '[1, 2]')


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.importer = default_importer()

    def test_dispatch_by_extension(self):
        rows = self.importer.parse('export.txt', TXT.encode('utf-8'))
        self.assertEqual(len(rows), 2)

    def test_bom_is_stripped(self):
        raw = '[{"id":"a","messages":[{"role":"user","content":"z"}]}]'
        rows = self.importer.parse('e.json', raw.encode('utf-8-sig'))
        self.assertEqual(rows[0].text, 'z')

    def test_unsupported_extension(self):
        with self.assertRaises(ValidationError):
            self.importer.parse('archive.zip', b'')

    def test_size_limit(self):
        small = default_importer(max_bytes=10)
        with self.assertRaises(ValidationError):
            small.parse('e.txt', b'x' * 11)


if __name__ == '__main__':
    unittest.main()
