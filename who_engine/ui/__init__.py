"""Слой интерфейса Streamlit. Логика находится в сервисах, не здесь.

Корень композиции импортируется лениво: модули без зависимости от Streamlit
(например, session) должны оставаться импортируемыми без него.
"""
from __future__ import annotations

from typing import Any

__all__ = ['build_app', 'main']


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import app

        return getattr(app, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
