"""Запуск приложения одной командой: python start.py

Готовит окружение (venv, зависимости, .env) и поднимает Streamlit.
Работает на Windows и macOS/Linux, нужен только установленный Python 3.11+.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
REQUIREMENTS = ROOT / 'requirements.txt'
ENTRYPOINT = 'streamlit_app.py'
HOST = '127.0.0.1'
PORT = '8501'
URL = f'http://{HOST}:{PORT}'
MIN_PYTHON = (3, 11)


def venv_python(root: Path = VENV) -> Path:
    """Путь к интерпретатору внутри venv: Scripts на Windows, bin на остальных."""
    folder = 'Scripts' if os.name == 'nt' else 'bin'
    suffix = '.exe' if os.name == 'nt' else ''
    return root / folder / f'python{suffix}'


def ensure_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f'Нужен Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} или новее, '
            f'установлен {sys.version.split()[0]}.')


def ensure_venv() -> Path:
    interpreter = venv_python()
    if interpreter.exists():
        return interpreter
    print('Создаю виртуальное окружение .venv …')
    venv.EnvBuilder(with_pip=True).create(VENV)
    if not interpreter.exists():
        raise SystemExit('Не удалось создать .venv. Текст ошибки выше.')
    return interpreter


def dependencies_present(interpreter: Path) -> bool:
    probe = subprocess.run(
        [str(interpreter), '-c', 'import streamlit, xai_sdk, dotenv'],
        capture_output=True)
    return probe.returncode == 0


def install_dependencies(interpreter: Path) -> None:
    print('Устанавливаю зависимости (один раз, может занять несколько минут) …')
    for args in (['-m', 'pip', 'install', '--upgrade', 'pip'],
                 ['-m', 'pip', 'install', '-r', str(REQUIREMENTS)]):
        if subprocess.run([str(interpreter), *args]).returncode != 0:
            raise SystemExit(
                'Ошибка установки. Скопируйте текст выше целиком — в нём причина.')


def ensure_env_file() -> None:
    target, example = ROOT / '.env', ROOT / '.env.example'
    if target.exists() or not example.exists():
        return
    shutil.copyfile(example, target)
    print(f'Создан {target.name}: впишите в него новый XAI_API_KEY. '
          'Без ключа приложение работает в офлайн-режиме.')


def wait_until_ready(timeout: float = 60.0) -> bool:
    """Ждёт готовности сервера, чтобы не открыть браузер на пустой странице."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f'{URL}/_stcore/health', timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def launch(interpreter: Path) -> int:
    """Сервер запускается в headless-режиме, браузер открываем сами."""
    print(f'Запускаю {URL} — остановить: Ctrl+C')
    command = [str(interpreter), '-m', 'streamlit', 'run', ENTRYPOINT,
               '--server.address', HOST, '--server.port', PORT]
    process = subprocess.Popen(command, cwd=ROOT)
    try:
        if wait_until_ready():
            webbrowser.open(URL)
        else:
            print(f'Сервер не ответил. Откройте {URL} вручную.')
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return 0


def main() -> int:
    ensure_python_version()
    interpreter = ensure_venv()
    if not dependencies_present(interpreter):
        install_dependencies(interpreter)
    ensure_env_file()
    return launch(interpreter)


if __name__ == '__main__':
    raise SystemExit(main())
