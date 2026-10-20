"""Приоритет источников ключа и формирование списка моделей."""
import unittest

from who_engine.config import Settings
from who_engine.domain import ModelInfo
from who_engine.ui.session import FROM_ENV, FROM_UI, MISSING, SessionStore


class CredentialTests(unittest.TestCase):
    def store(self, state=None, **kwargs):
        return SessionStore(state if state is not None else {},
                            Settings(**kwargs))

    def test_no_key_anywhere(self):
        creds = self.store().credentials()
        self.assertFalse(creds.present)
        self.assertEqual(creds.source, MISSING)

    def test_env_key_used_when_nothing_entered(self):
        creds = self.store(api_key='xai-env').credentials()
        self.assertEqual(creds.api_key, 'xai-env')
        self.assertEqual(creds.source, FROM_ENV)

    def test_interface_key_overrides_env(self):
        state = {}
        store = self.store(state, api_key='xai-env')
        store.set_api_key('  xai-ui  ')
        creds = store.credentials()
        self.assertEqual(creds.api_key, 'xai-ui')
        self.assertEqual(creds.source, FROM_UI)

    def test_clearing_falls_back_to_env(self):
        store = self.store({}, api_key='xai-env')
        store.set_api_key('xai-ui')
        store.clear_api_key()
        self.assertEqual(store.credentials().source, FROM_ENV)

    def test_blank_entry_is_not_an_override(self):
        store = self.store({}, api_key='xai-env')
        store.set_api_key('   ')
        self.assertEqual(store.credentials().source, FROM_ENV)

    def test_key_never_leaves_session_state(self):
        state = {}
        store = self.store(state, api_key='')
        store.set_api_key('xai-secret')
        self.assertIn('xai-secret', state.values())
        self.assertEqual(len(state), 1)


class ModelOptionTests(unittest.TestCase):
    def test_default_model_when_nothing_loaded(self):
        store = SessionStore({}, Settings(model='grok-4.7'))
        self.assertEqual(store.model(), 'grok-4.7')
        self.assertEqual(store.model_options(), ['grok-4.7'])

    def test_catalog_populates_options(self):
        store = SessionStore({}, Settings(model='grok-4.7'))
        store.set_catalog([ModelInfo('grok-3'), ModelInfo('grok-4.7')])
        self.assertEqual(store.model_options(), ['grok-3', 'grok-4.7'])

    def test_manual_model_is_kept_in_options(self):
        store = SessionStore({}, Settings(model='grok-4.7'))
        store.set_catalog([ModelInfo('grok-3')])
        store.set_model('grok-experimental')
        self.assertEqual(store.model_options(),
                         ['grok-3', 'grok-experimental', 'grok-4.7'])

    def test_blank_model_is_ignored(self):
        store = SessionStore({}, Settings(model='grok-4.7'))
        store.set_model('  ')
        self.assertEqual(store.model(), 'grok-4.7')


if __name__ == '__main__':
    unittest.main()
