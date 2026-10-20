"""Адаптер xAI SDK. SDK импортируется лениво: без ключа он не нужен."""
from __future__ import annotations

from typing import Any, Sequence

from ..domain import ChatMessage, ChatReply, Role
from ..errors import ConfigurationError, ProviderError
from .base import normalize_usage


class XaiChatClient:
    """Следует документированному API: Client → chat.create → append → sample."""

    def __init__(self, api_key: str, timeout: int = 120) -> None:
        if not api_key.strip():
            raise ConfigurationError('В .env отсутствует XAI_API_KEY')
        self._api_key = api_key
        self._timeout = timeout

    def complete(self, messages: Sequence[ChatMessage], model: str) -> ChatReply:
        client_factory, constructors = self._load_sdk()
        client = client_factory(api_key=self._api_key, timeout=self._timeout)
        chat = client.chat.create(model=model)
        for message in messages:
            chat.append(constructors[message.role](message.content))
        # Без скрытых автоповторов: платный неоднозначный запрос требует
        # явного решения оператора.
        response = chat.sample()
        return self._to_reply(response, model)

    @staticmethod
    def _load_sdk() -> tuple[Any, dict[Role, Any]]:
        from xai_sdk import Client
        from xai_sdk.chat import system, user
        try:
            from xai_sdk.chat import assistant
        except ImportError as exc:
            raise ProviderError(
                'Текущая версия xai-sdk не содержит assistant(); обновите '
                'xai-sdk или сообщите версию пакета') from exc
        return Client, {
            Role.SYSTEM: system,
            Role.USER: user,
            Role.ASSISTANT: assistant,
        }

    @staticmethod
    def _to_reply(response: Any, requested_model: str) -> ChatReply:
        return ChatReply(
            content=str(getattr(response, 'content', '') or ''),
            model=str(getattr(response, 'model', None) or requested_model),
            usage=normalize_usage(getattr(response, 'usage', None)),
            request_id=str(getattr(response, 'id', '') or ''),
        )
