"""Адаптеры провайдеров модели."""
from .base import (AccountInspector, ChatClient, ModelCatalog, NullProvider,
                   Provider)
from .xai import XaiProvider

__all__ = ['AccountInspector', 'ChatClient', 'ModelCatalog', 'NullProvider',
           'Provider', 'XaiProvider']


def build_provider(api_key: str, timeout: int = 120) -> Provider:
    """Фабрика: без ключа — офлайн-провайдер, с ключом — xAI."""
    if not api_key.strip():
        return NullProvider()
    return XaiProvider(api_key, timeout=timeout)
