import asyncio

from app.core.logging_mixin import LoggerMixin
from app.modules.enrichment.domain.usecases.enrich_one import EnrichOneUseCase
from app.modules.ingestion.domain.repository import MentionRepo


class EnrichWorker(LoggerMixin):
    def __init__(self, repo: MentionRepo, enrich_one: EnrichOneUseCase, concurrency: int) -> None:
        self.repo = repo
        self.enrich_one = enrich_one
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(concurrency)
        self._task: asyncio.Task[None] | None = None
        self._process_tasks: set[asyncio.Task[None]] = set()
        self._stopping = False

    def enqueue(self, mention_id: str) -> None:
        self.queue.put_nowait(mention_id)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stopping:
            mention_id = await self.queue.get()
            task = asyncio.create_task(self._process(mention_id))
            self._process_tasks.add(task)
            task.add_done_callback(self._process_tasks.discard)

    async def _process(self, mention_id: str) -> None:
        async with self.semaphore:
            try:
                mention = await self.repo.get(mention_id)
                if mention is None:
                    self.logger.warning("Mention %s not found", mention_id)
                    return
                fields = await self.enrich_one.execute(mention)
                await self.repo.set_enrichment(mention_id, fields)
            except Exception as exc:
                self.log_exception("Failed to enrich mention %s", mention_id)
                await self.repo.mark_failed(mention_id, str(exc))
            finally:
                self.queue.task_done()

    async def recover_pending(self) -> int:
        ids = await self.repo.find_pending_ids()
        for mention_id in ids:
            self.enqueue(mention_id)
        return len(ids)

    async def retry_failed(self) -> int:
        ids = await self.repo.find_failed_ids()
        for mention_id in ids:
            self.enqueue(mention_id)
        return len(ids)
