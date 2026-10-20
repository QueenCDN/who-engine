"""Один явный платный тестовый запрос через xAI SDK."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from who_engine.config import load_settings
from who_engine.domain import ChatMessage, Role
from who_engine.providers import XaiChatClient

settings = load_settings()

if not settings.has_api_key:
    raise SystemExit(
        'XAI_API_KEY missing. '
        'Create .env in the project root and add a NEW key.'
    )

answer = input(
    f'Отправить ОДИН платный тестовый запрос к {settings.model}? [yes/no] '
).strip().lower()

if answer != 'yes':
    raise SystemExit('Отменено')

client = XaiChatClient(settings.api_key, timeout=settings.request_timeout)
reply = client.complete(
    [ChatMessage(Role.USER, 'Ответь одним словом: связь')],
    settings.model,
)

print('Model:', reply.model)
print('Answer:', reply.content)
print('Request ID:', reply.request_id)
print('Usage:', reply.usage)
