"""Прикладные сценарии. Не импортируют Streamlit: интерфейс заменяем."""
from __future__ import annotations

from pathlib import Path

from .archive import ArchiveImporter, XaiMetadataParser
from .domain import (ApiKeyInfo, Arm, ChatMessage, ConversationSummary,
                     ImportResult, ModelInfo, Note, ProbeResult, Role, Run,
                     SourceHit, SourceMessage, Turn, TurnStatus)
from .errors import WhoEngineError
from .prompts import PromptComposer
from .providers import AccountInspector, ChatClient, ModelCatalog
from .storage.base import (BackupRepository, ExportRepository, NoteRepository,
                           RunRepository, SourceRepository, TurnRepository)


class UncertainRequest(WhoEngineError):
    """Запрос мог дойти до сервера. Автоповтор запрещён."""


class ExperimentService:
    """Создание экспериментов и отправка одной реплики."""

    def __init__(self,
                 runs: RunRepository,
                 turns: TurnRepository,
                 client: ChatClient,
                 composer: PromptComposer) -> None:
        self._runs = runs
        self._turns = turns
        self._client = client
        self._composer = composer

    @property
    def composer(self) -> PromptComposer:
        return self._composer

    def create_run(self, title: str, arm: Arm, model: str) -> str:
        return self._runs.create_run(title, arm.label, model)

    def list_runs(self) -> list[Run]:
        return self._runs.list_runs()

    def transcript(self, run_id: str) -> list[Turn]:
        return self._turns.list_turns(run_id)

    def run_size(self, run_id: str) -> tuple[int, int]:
        return self._runs.run_size(run_id)

    def delete_run(self, run_id: str) -> None:
        """Удаляет эксперимент вместе с его репликами и наблюдениями.

        Операция необратима и не трогает импортированный архив.
        """
        self._runs.delete_run(run_id)

    def validate_archive(self, arm: Arm, passages: str) -> None:
        self._composer.check_archive_length(arm, passages)

    def send(self, run: Run, prompt: str, passages: str = '') -> Turn:
        """Пишет реплику пользователя, затем ровно один запрос к модели.

        При любом сбое реплика остаётся в статусе uncertain: ответ мог быть
        сгенерирован и оплачен, поэтому решение о повторе принимает оператор.
        """
        self.validate_archive(run.arm, passages)
        history = self._history(run.id)
        messages = self._composer.build(run.arm, history, prompt, passages)
        user_turn_id = self._turns.add_turn(
            run.id, Role.USER, prompt, TurnStatus.INFLIGHT)
        try:
            reply = self._client.complete(messages, run.model)
        except Exception as exc:
            self._turns.update_turn(
                user_turn_id, TurnStatus.UNCERTAIN, error=str(exc))
            raise UncertainRequest(str(exc)) from exc
        self._turns.update_turn(user_turn_id, TurnStatus.COMPLETE)
        answer_id = self._turns.add_turn(
            run.id, Role.ASSISTANT, reply.content, TurnStatus.COMPLETE,
            model=reply.model, usage=reply.usage, request_id=reply.request_id)
        return Turn(answer_id, Role.ASSISTANT, reply.content,
                    TurnStatus.COMPLETE, created='', model=reply.model)

    def _history(self, run_id: str) -> list[ChatMessage]:
        return [ChatMessage(turn.role, turn.content)
                for turn in self._turns.list_turns(run_id)
                if turn.is_complete and turn.role in Role.dialogue()]


class ArchiveService:
    """Импорт и локальный просмотр архива. В API ничего не уходит."""

    def __init__(self,
                 source: SourceRepository,
                 importer: ArchiveImporter,
                 conversation_id: str,
                 metadata_parser: XaiMetadataParser | None = None) -> None:
        self._source = source
        self._importer = importer
        self._conversation_id = conversation_id
        self._metadata_parser = metadata_parser or XaiMetadataParser()

    @property
    def supported_types(self) -> tuple[str, ...]:
        return self._importer.supported

    def import_file(self, filename: str, content: bytes) -> ImportResult:
        records = self._importer.parse(filename, content)
        if not records:
            return ImportResult(recognized=0, added=0)
        added = self._source.save_records(records)
        self._save_metadata(filename, content)
        return ImportResult(recognized=len(records), added=added)

    def _save_metadata(self, filename: str, content: bytes) -> None:
        if not filename.lower().endswith('.json'):
            return
        items = self._metadata_parser.parse(content.decode('utf-8-sig'))
        self._source.save_metadata(items)

    def total_messages(self) -> int:
        return self._source.count(self._conversation_id)

    def conversations(self) -> list[ConversationSummary]:
        return self._source.summaries(self._conversation_id)

    def preview(self, conversation_id: str,
                limit: int = 5) -> list[SourceMessage]:
        return self._source.messages(conversation_id, limit)

    def search(self, query: str) -> list[SourceHit]:
        return self._source.search(self._conversation_id, query)


class ObservationService:
    """Журнал наблюдений и экспорт эксперимента."""

    def __init__(self, notes: NoteRepository, export: ExportRepository) -> None:
        self._notes = notes
        self._export = export

    def add_note(self, run_id: str, label: str, observation: str,
                 interpretation: str, confidence: str) -> None:
        self._notes.add_note(run_id, label, observation, interpretation,
                             confidence)

    def notes(self, run_id: str) -> list[Note]:
        return self._notes.list_notes(run_id)

    def export(self, run_id: str) -> str:
        return self._export.export_run(run_id)


class BackupService:
    def __init__(self, repository: BackupRepository) -> None:
        self._repository = repository

    def create(self) -> Path:
        return self._repository.backup()


class DiagnosticsService:
    """Проверка связи с xAI: бесплатные вызовы отделены от платного."""

    PROBE_PROMPT = 'Ответь одним словом: связь'

    def __init__(self, inspector: AccountInspector, catalog: ModelCatalog,
                 chat: ChatClient) -> None:
        self._inspector = inspector
        self._catalog = catalog
        self._chat = chat

    def check_key(self) -> ApiKeyInfo:
        """Бесплатно: подтверждает, что ключ принят и не заблокирован."""
        return self._inspector.key_info()

    def models(self) -> list[ModelInfo]:
        """Бесплатно: перечень моделей, доступных этому ключу."""
        return self._catalog.language_models()

    def probe(self, model: str) -> ProbeResult:
        """Платно: один минимальный запрос, подтверждающий доступ к модели."""
        reply = self._chat.complete(
            [ChatMessage(Role.USER, self.PROBE_PROMPT)], model)
        return ProbeResult(model=reply.model, answer=reply.content,
                           usage=reply.usage, request_id=reply.request_id)
