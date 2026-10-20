"""Условия A/B/C/D: что попадает в системный промпт, а что нет."""
import unittest

from who_engine.domain import Arm, ChatMessage, Role
from who_engine.errors import ValidationError
from who_engine.prompts import PromptComposer


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.composer = PromptComposer()

    def system_text(self, arm, passages=''):
        return self.composer.build(arm, [], 'привет', passages)[0].content

    def test_clean_arm_never_receives_archive(self):
        self.assertNotIn('АРХИВ', self.system_text(Arm.CLEAN, 'секрет'))
        self.assertNotIn('секрет', self.system_text(Arm.CLEAN, 'секрет'))

    def test_history_arm_receives_archive(self):
        self.assertIn('секрет', self.system_text(Arm.HISTORY, 'секрет'))

    def test_operator_fragments(self):
        self.assertIn('HOW', self.composer.system_prompt(Arm.DESCRIPTION))
        self.assertIn('G3', self.composer.system_prompt(Arm.PROCEDURE_G3))
        self.assertNotIn('G3', self.composer.system_prompt(Arm.DESCRIPTION))

    def test_blank_archive_adds_no_header(self):
        self.assertNotIn('АРХИВ', self.system_text(Arm.HISTORY, '   '))

    def test_archive_limit(self):
        with self.assertRaises(ValidationError):
            self.composer.build(Arm.HISTORY, [], 'привет', 'x' * 8001)

    def test_unknown_arm_label(self):
        with self.assertRaises(ValidationError):
            Arm.from_label('E — нет такой')

    def test_history_is_trimmed_and_filtered(self):
        history = [ChatMessage(Role.SYSTEM, 'служебное')]
        history += [ChatMessage(Role.USER, f'm{i}') for i in range(20)]
        messages = self.composer.build(Arm.CLEAN, history, 'вопрос')
        self.assertEqual(messages[0].role, Role.SYSTEM)
        self.assertEqual(messages[-1].content, 'вопрос')
        self.assertEqual(len(messages), 1 + 12 + 1)
        self.assertNotIn('служебное', [m.content for m in messages])


if __name__ == '__main__':
    unittest.main()
