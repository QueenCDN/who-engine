"""Устойчивость импорта.

Streamlit выполняет скрипт в отдельном потоке на каждую сессию, поэтому
первый импорт дерева зависимостей может случиться одновременно из нескольких
потоков. Ленивый импорт в `who_engine/ui/__init__.py` приводил в этих условиях
к `KeyError: 'who_engine.storage.base'`.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_snippet(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-c', code], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=180)


def streamlit_available() -> bool:
    return run_snippet('import streamlit').returncode == 0


class LightweightImportTests(unittest.TestCase):
    """Пакет ui не должен тянуть Streamlit: иначе его модули не протестировать."""

    def test_ui_package_itself_imports_nothing_heavy(self):
        result = run_snippet(
            'import sys, who_engine.ui;'
            " sys.exit(1 if 'streamlit' in sys.modules else 0)")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_module_imports_without_streamlit(self):
        result = run_snippet(
            'import sys, who_engine.ui.session;'
            " sys.exit(1 if 'streamlit' in sys.modules else 0)")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_router_imports_without_streamlit(self):
        result = run_snippet(
            'import sys, who_engine.ui.base;'
            " sys.exit(1 if 'streamlit' in sys.modules else 0)")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ui_package_defines_no_lazy_getattr(self):
        """Ленивый __getattr__ уводил импорт дерева в поток сессии."""
        result = run_snippet(
            'import who_engine.ui as m, sys;'
            " sys.exit(1 if hasattr(m, '__getattr__') else 0)")
        self.assertEqual(result.returncode, 0, result.stderr)


CONCURRENT = '''
import sys, threading
errors = []

def work():
    try:
        import who_engine.ui.app  # noqa: F401
    except BaseException as exc:
        errors.append(repr(exc))

threads = [threading.Thread(target=work) for _ in range(8)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
if errors:
    print(errors[0])
    sys.exit(1)
'''


class ConcurrentImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not streamlit_available():
            raise unittest.SkipTest('streamlit не установлен в этом интерпретаторе')

    def test_parallel_first_import_succeeds(self):
        result = run_snippet(CONCURRENT)
        self.assertEqual(result.returncode, 0,
                         f'одновременный импорт упал: {result.stdout}{result.stderr}')

    def test_entrypoint_imports_main(self):
        result = run_snippet('from who_engine.ui.app import main; assert callable(main)')
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
