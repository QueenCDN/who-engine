"""Выбор парсера по расширению файла."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from ..domain import ArchiveRecord
from ..errors import ValidationError
from .base import ArchiveParser
from .json_export import GrokJsonParser
from .txt import GrokTxtParser


class ArchiveImporter:
    """Реестр парсеров: новый формат регистрируется, а не вшивается в условия."""

    def __init__(self,
                 parsers: Sequence[ArchiveParser],
                 max_bytes: int = 100 * 1024 * 1024) -> None:
        self._parsers: Mapping[str, ArchiveParser] = {
            parser.suffix: parser for parser in parsers}
        self._max_bytes = max_bytes

    @property
    def supported(self) -> tuple[str, ...]:
        return tuple(suffix.lstrip('.') for suffix in self._parsers)

    def parse(self, filename: str, content: bytes) -> list[ArchiveRecord]:
        self._check_size(content)
        parser = self._parser_for(filename)
        return parser.parse(content.decode('utf-8-sig'))

    def _check_size(self, content: bytes) -> None:
        if len(content) > self._max_bytes:
            raise ValidationError(
                'Файл больше 100 МБ. Разделите его без изменений содержания.')

    def _parser_for(self, filename: str) -> ArchiveParser:
        suffix = Path(filename).suffix.lower()
        parser = self._parsers.get(suffix)
        if parser is None:
            raise ValidationError(
                'Поддерживаются только .txt или .json; ZIP сначала распаковать локально')
        return parser


def default_importer(max_bytes: int = 100 * 1024 * 1024) -> ArchiveImporter:
    return ArchiveImporter((GrokTxtParser(), GrokJsonParser()), max_bytes)
