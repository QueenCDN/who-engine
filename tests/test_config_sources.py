"""Источники конфигурации и порядок их приоритета."""
import os
import tempfile
import unittest
from pathlib import Path

from who_engine.config import (ChainedSource, DEFAULT_MODEL, EnvSource,
                               SectionedSecretsSource, Settings,
                               StreamlitSecretsSource, env_var_present,
                               load_settings, secret_names,
                               secret_section_holding)


class FakeSource:
    def __init__(self, values):
        self.values = values
        self.reads = []

    def get(self, key):
        self.reads.append(key)
        return self.values.get(key)


class ChainTests(unittest.TestCase):
    def test_first_non_empty_wins(self):
        first = FakeSource({'K': ''})
        second = FakeSource({'K': 'из второго'})
        third = FakeSource({'K': 'из третьего'})
        chain = ChainedSource((first, second, third))
        self.assertEqual(chain.get('K'), 'из второго')
        self.assertEqual(third.reads, [], 'третий источник не должен опрашиваться')

    def test_missing_everywhere_gives_none(self):
        self.assertIsNone(ChainedSource((FakeSource({}),)).get('K'))

    def test_empty_chain_gives_none(self):
        self.assertIsNone(ChainedSource(()).get('K'))


class SettingsTests(unittest.TestCase):
    def test_defaults_when_nothing_configured(self):
        settings = load_settings(source=FakeSource({}))
        self.assertFalse(settings.has_api_key)
        self.assertEqual(settings.model, DEFAULT_MODEL)

    def test_values_are_read(self):
        settings = load_settings(
            source=FakeSource({'XAI_API_KEY': 'xai-тест', 'XAI_MODEL': 'grok-9'}))
        self.assertTrue(settings.has_api_key)
        self.assertEqual(settings.model, 'grok-9')

    def test_blank_key_is_not_a_key(self):
        self.assertFalse(Settings(api_key='   ').has_api_key)


class WithoutStreamlitTests(unittest.TestCase):
    """Вне Streamlit источники секретов обязаны молчать, а не падать."""

    def test_streamlit_source_returns_none(self):
        self.assertIsNone(StreamlitSecretsSource().get('XAI_API_KEY'))

    def test_sectioned_source_returns_none(self):
        self.assertIsNone(SectionedSecretsSource().get('XAI_API_KEY'))

    def test_secret_helpers_are_safe(self):
        self.assertEqual(secret_names(), ())
        self.assertIsNone(secret_section_holding('XAI_API_KEY'))


class EnvTests(unittest.TestCase):
    def test_env_source_reads_environment(self):
        os.environ['WHO_ENGINE_TEST_KEY'] = 'значение'
        try:
            self.assertEqual(EnvSource().get('WHO_ENGINE_TEST_KEY'), 'значение')
            self.assertTrue(env_var_present('WHO_ENGINE_TEST_KEY'))
        finally:
            os.environ.pop('WHO_ENGINE_TEST_KEY', None)
        self.assertFalse(env_var_present('WHO_ENGINE_TEST_KEY'))

    def test_missing_dotenv_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = load_settings(root=Path(tmp))
            self.assertIsInstance(settings, Settings)


if __name__ == '__main__':
    unittest.main()
