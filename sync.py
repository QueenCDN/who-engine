"""Отправка текущего состояния в оба репозитория: python sync.py

Приватный репозиторий заказчицы (`origin`) хранит полную историю разработки.
Публичный (`public`), из которого идёт деплой на Streamlit Cloud, хранит
только снимки кода: его история начата заново, потому что в первом коммите
проекта лежал действующий API-ключ, и переносить такую историю в публичный
репозиторий нельзя.

Поэтому коммиты в репозиториях разные, а содержимое одинаковое, и один
`git push` обслужить оба не может. Скрипт отправляет коммит в приватный,
создаёт поверх публичного снимок с тем же деревом файлов и проверяет, что
деревья совпали.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Консоль Windows по умолчанию не cp65001: без этого вывод падает на любом
# символе вне кодовой страницы — в том числе на кириллице в сообщении коммита.
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, 'reconfigure', None)
    if reconfigure is not None:
        reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent
PRIVATE = 'origin'
PUBLIC = 'public'
BRANCH = 'main'


class SyncError(RuntimeError):
    """Остановка до любых изменений в удалённых репозиториях."""


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    if check and result.returncode != 0:
        raise SyncError(f'git {" ".join(args)}\n{result.stderr.strip()}')
    return result.stdout.strip()


def require_clean_tree() -> None:
    if git('status', '--porcelain'):
        raise SyncError('Есть незакоммиченные изменения. Сначала закоммитьте их.')


def require_remotes() -> None:
    remotes = git('remote').split()
    missing = [name for name in (PRIVATE, PUBLIC) if name not in remotes]
    if missing:
        raise SyncError(f'Не настроены удалённые репозитории: {", ".join(missing)}')


def tree_of(ref: str) -> str:
    return git('rev-parse', f'{ref}^{{tree}}')


def push_private(dry_run: bool) -> None:
    local = git('rev-parse', BRANCH)
    remote = git('rev-parse', f'{PRIVATE}/{BRANCH}')
    if local == remote:
        print(f'{PRIVATE}: уже актуален')
        return
    if dry_run:
        print(f'{PRIVATE}: будет отправлено {remote[:7]} -> {local[:7]}')
        return
    git('push', PRIVATE, f'{BRANCH}:{BRANCH}')
    print(f'{PRIVATE}: отправлено {remote[:7]} -> {local[:7]}')


def push_public(dry_run: bool) -> None:
    """Снимок поверх публичной истории: то же дерево, новый коммит."""
    if tree_of(BRANCH) == tree_of(f'{PUBLIC}/{BRANCH}'):
        print(f'{PUBLIC}: содержимое уже совпадает, снимок не нужен')
        return
    message = git('log', '-1', '--format=%B', BRANCH)
    if dry_run:
        first_line = message.splitlines()[0] if message else ''
        print(f'{PUBLIC}: будет создан снимок «{first_line}»')
        return
    snapshot = git('commit-tree', tree_of(BRANCH),
                   '-p', git('rev-parse', f'{PUBLIC}/{BRANCH}'),
                   '-m', message)
    git('push', PUBLIC, f'{snapshot}:{BRANCH}')
    print(f'{PUBLIC}: отправлен снимок {snapshot[:7]}')


def verify() -> None:
    git('fetch', PRIVATE, BRANCH, '-q')
    git('fetch', PUBLIC, BRANCH, '-q')
    local = tree_of(BRANCH)
    checks = {
        PRIVATE: tree_of(f'{PRIVATE}/{BRANCH}'),
        PUBLIC: tree_of(f'{PUBLIC}/{BRANCH}'),
    }
    for name, tree in checks.items():
        status = 'совпадает' if tree == local else 'РАСХОЖДЕНИЕ'
        print(f'проверка {name}: {status}')
    if any(tree != local for tree in checks.values()):
        raise SyncError('Содержимое репозиториев разошлось.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='показать, что будет отправлено, и ничего не менять')
    dry_run = parser.parse_args().dry_run
    try:
        require_remotes()
        require_clean_tree()
        git('fetch', PRIVATE, BRANCH, '-q')
        git('fetch', PUBLIC, BRANCH, '-q')
        push_private(dry_run)
        push_public(dry_run)
        if not dry_run:
            verify()
    except SyncError as error:
        print(f'Остановлено: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
