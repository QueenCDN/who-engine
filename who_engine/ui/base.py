"""Контракт раздела интерфейса и маршрутизация без ветвлений."""
from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable


@runtime_checkable
class Page(Protocol):
    """Один раздел бокового меню."""

    label: str

    def render(self) -> None:
        ...


class PageRouter:
    """Выбирает раздел по метке.

    Новый раздел добавляется в список страниц; здесь ничего не меняется.
    """

    def __init__(self, pages: Sequence[Page]) -> None:
        if not pages:
            raise ValueError('Нужен хотя бы один раздел')
        self._pages: Mapping[str, Page] = {page.label: page for page in pages}

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(self._pages)

    @property
    def default(self) -> str:
        return self.labels[0]

    def render(self, label: str) -> None:
        self._pages[label if label in self._pages else self.default].render()
