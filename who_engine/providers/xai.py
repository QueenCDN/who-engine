"""Адаптер xAI SDK. SDK импортируется лениво: без ключа он не нужен."""
from __future__ import annotations

from typing import Any, Sequence

from ..domain import ApiKeyInfo, ChatMessage, ChatReply, ModelInfo, Role
from ..errors import ConfigurationError, ProviderError
from .base import NO_KEY, normalize_usage


class XaiProvider:
    """Следует документированному API: Client → chat.create → append → sample.

    Соединение создаётся на каждый вызов и закрывается: интерфейс
    пересоздаёт провайдера при смене ключа.
    """

    available = True

    def __init__(self, api_key: str, timeout: int = 120) -> None:
        if not api_key.strip():
            raise ConfigurationError(NO_KEY)
        self._api_key = api_key
        self._timeout = timeout

    # --- чат ----------------------------------------------------------------

    def complete(self, messages: Sequence[ChatMessage], model: str) -> ChatReply:
        constructors = self._message_constructors()
        client = self._client()
        try:
            chat = client.chat.create(model=model)
            for message in messages:
                chat.append(constructors[message.role](message.content))
            # Без скрытых автоповторов: платный неоднозначный запрос требует
            # явного решения оператора.
            response = chat.sample()
        finally:
            self._close(client)
        return self._to_reply(response, model)

    # --- бесплатные справочные вызовы ---------------------------------------

    def language_models(self) -> list[ModelInfo]:
        """Перечень моделей. Токены не расходуются."""
        client = self._client()
        try:
            raw = client.models.list_language_models()
        except Exception as exc:
            raise ProviderError(self._explain(exc)) from exc
        finally:
            self._close(client)
        return sorted((self._to_model(item) for item in raw),
                      key=lambda model: model.name)

    def key_info(self) -> ApiKeyInfo:
        """Проверка ключа. Токены не расходуются."""
        client = self._client()
        try:
            raw = client.auth.get_api_key_info()
        except Exception as exc:
            raise ProviderError(self._explain(exc)) from exc
        finally:
            self._close(client)
        return ApiKeyInfo(
            redacted=str(getattr(raw, 'redacted_api_key', '') or ''),
            name=str(getattr(raw, 'name', '') or ''),
            blocked=bool(getattr(raw, 'api_key_blocked', False)
                         or getattr(raw, 'team_blocked', False)),
            disabled=bool(getattr(raw, 'disabled', False)),
            acls=tuple(str(item) for item in getattr(raw, 'acls', ()) or ()),
        )

    # --- внутреннее ---------------------------------------------------------

    def _client(self) -> Any:
        from xai_sdk import Client

        return Client(api_key=self._api_key, timeout=self._timeout)

    @staticmethod
    def _close(client: Any) -> None:
        closer = getattr(client, 'close', None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass

    @staticmethod
    def _message_constructors() -> dict[Role, Any]:
        from xai_sdk.chat import system, user
        try:
            from xai_sdk.chat import assistant
        except ImportError as exc:
            raise ProviderError(
                'Текущая версия xai-sdk не содержит assistant(); обновите '
                'xai-sdk или сообщите версию пакета') from exc
        return {Role.SYSTEM: system, Role.USER: user, Role.ASSISTANT: assistant}

    @staticmethod
    def _to_reply(response: Any, requested_model: str) -> ChatReply:
        return ChatReply(
            content=str(getattr(response, 'content', '') or ''),
            model=str(getattr(response, 'model', None) or requested_model),
            usage=normalize_usage(getattr(response, 'usage', None)),
            request_id=str(getattr(response, 'id', '') or ''),
        )

    @staticmethod
    def _to_model(item: Any) -> ModelInfo:
        return ModelInfo(
            name=str(getattr(item, 'name', '') or ''),
            aliases=tuple(str(a) for a in getattr(item, 'aliases', ()) or ()),
            version=str(getattr(item, 'version', '') or ''),
            max_prompt_length=int(getattr(item, 'max_prompt_length', 0) or 0),
            prompt_price=int(getattr(item, 'prompt_text_token_price', 0) or 0),
            completion_price=int(getattr(item, 'completion_text_token_price', 0) or 0),
        )

    @staticmethod
    def _explain(exc: Exception) -> str:
        """Делает типовые ответы gRPC понятными без чтения трассировки."""
        text = str(exc)
        hints = (
            ('UNAUTHENTICATED', 'Ключ не принят: проверьте, что он действующий и скопирован целиком.'),
            ('PERMISSION_DENIED', 'Ключу не хватает прав на этот вызов.'),
            ('NOT_FOUND', 'Запрошенный ресурс недоступен этому ключу.'),
            ('UNAVAILABLE', 'Сервис недоступен или нет сети.'),
            ('DEADLINE_EXCEEDED', 'Истекло время ожидания ответа.'),
        )
        for marker, hint in hints:
            if marker in text:
                return f'{hint} ({marker})'
        return text
