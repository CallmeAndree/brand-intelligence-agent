import asyncio
from collections.abc import Awaitable, Callable

from app.core.errors import is_rate_limit_error
from app.core.logging_mixin import LoggerMixin
from app.modules.enrichment.domain.models import (
    BiFields,
    JudgmentFields,
    SummaryField,
    TopicFields,
)
from app.modules.enrichment.domain.usecases.enrich_one import EnrichOneUseCase
from app.modules.ingestion.domain.models import Mention
from app.modules.ingestion.domain.repository import MentionRepo

# Gán cụm cho 1 mention: (mention_id, fields enrich, topic vector). None = tắt incremental.
AssignClustersFn = Callable[[str, BiFields, list[float]], Awaitable[None]]


class EnrichWorker(LoggerMixin):
    def __init__(
        self,
        repo: MentionRepo,
        enrich_one: EnrichOneUseCase,
        embed: Callable[[list[str]], Awaitable[list[list[float]]]],
        concurrency: int,
        retry_delay: float = 300.0,
        max_attempts: int = 5,
        assign_clusters: AssignClustersFn | None = None,
    ) -> None:
        self.repo = repo
        self.enrich_one = enrich_one
        self.embed = embed
        self.retry_delay = retry_delay
        self.max_attempts = max_attempts
        self.assign_clusters = assign_clusters
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(concurrency)
        # Gán cụm đọc-sửa state cụm dùng chung → serialize bằng lock (1 replica).
        self._cluster_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._process_tasks: set[asyncio.Task[None]] = set()
        self._retry_tasks: set[asyncio.Task[None]] = set()
        self._attempts: dict[str, int] = {}
        self._stopping = False

    def enqueue(self, mention_id: str) -> None:
        self.queue.put_nowait(mention_id)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        for task in list(self._retry_tasks):
            task.cancel()
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
                fields, topic_vec = await self._enrich_incremental(mention)
                await self.repo.mark_enriched(mention_id)
                self._attempts.pop(mention_id, None)
                await self._assign_clusters(mention_id, fields, topic_vec)
            except Exception as exc:
                await self._handle_failure(mention_id, exc)
            finally:
                self.queue.task_done()

    async def _enrich_incremental(self, mention: Mention) -> tuple[BiFields, list[float]]:
        # Gọi được pass nào → save_partial ngay pass đó (status vẫn pending). Mỗi
        # pass đã có trong document (resume) thì BỎ QUA, không gọi lại LLM. Nhờ vậy
        # 429 ở pass sau không xoá công của pass trước, retry chỉ chạy phần còn thiếu.
        mid = mention.id
        topic = self._resume_topic(mention)
        if topic is None:
            topic = await self.enrich_one.topic(mention)
            await self.repo.save_partial(mid, topic.model_dump())

        judgment = self._resume_judgment(mention)
        if judgment is None:
            judgment = await self.enrich_one.judgment(mention, topic)
            await self.repo.save_partial(mid, judgment.model_dump())

        summary = self._resume_summary(mention)
        if summary is None:
            summary = await self.enrich_one.summary(mention, topic)
            await self.repo.save_partial(mid, summary.model_dump())

        fields = BiFields(**topic.model_dump(), **judgment.model_dump(), **summary.model_dump())

        topic_vec = mention.embedding
        if topic_vec is None or mention.summary_embedding is None:
            # 1 gateway call cho 2 vector: topic (cluster/issue) + summary (chat semantic search)
            topic_vec, summary_vec = await self.embed([fields.bi_topic, fields.bi_summary_vi])
            await self.repo.save_partial(
                mid, {"embedding": topic_vec, "summary_embedding": summary_vec}
            )
        return fields, topic_vec

    @staticmethod
    def _resume_topic(mention: Mention) -> TopicFields | None:
        if mention.bi_topic and mention.bi_product_area:
            return TopicFields(
                bi_topic=mention.bi_topic,
                bi_product_area=mention.bi_product_area,
                bi_keywords=mention.bi_keywords or [],
            )
        return None

    @staticmethod
    def _resume_judgment(mention: Mention) -> JudgmentFields | None:
        if (
            mention.bi_severity is not None
            and mention.bi_intent
            and mention.bi_is_actionable is not None
        ):
            return JudgmentFields(
                bi_severity=mention.bi_severity,
                bi_intent=mention.bi_intent,
                bi_is_actionable=mention.bi_is_actionable,
            )
        return None

    @staticmethod
    def _resume_summary(mention: Mention) -> SummaryField | None:
        if mention.bi_summary_vi:
            return SummaryField(bi_summary_vi=mention.bi_summary_vi)
        return None

    async def _assign_clusters(self, mention_id: str, fields: BiFields, topic_vec: list[float]) -> None:
        # Enrich đã ghi done ở trên — bước gán cụm là phụ trợ: lỗi ở đây CHỈ log,
        # KHÔNG được bubble lên (sẽ bị _handle_failure mark_failed nhầm).
        if self.assign_clusters is None:
            return
        try:
            async with self._cluster_lock:
                await self.assign_clusters(mention_id, fields, topic_vec)
        except Exception:
            self.log_exception("Gán cụm cho mention %s thất bại — bỏ qua, enrich vẫn done", mention_id)

    async def _handle_failure(self, mention_id: str, exc: Exception) -> None:
        # 429 rate-limit: transient thuần — giữ pending, thử lại MÃI cho tới khi
        # gateway cho qua. Không tính vào cap, không bao giờ mark_failed.
        if is_rate_limit_error(exc):
            self.logger.warning(
                "Mention %s gặp rate-limit (429) — giữ pending, thử lại sau %.0fs",
                mention_id,
                self.retry_delay,
            )
            self._schedule_retry(mention_id)
            return

        attempts = self._attempts.get(mention_id, 0) + 1
        self._attempts[mention_id] = attempts
        if attempts >= self.max_attempts:
            self._attempts.pop(mention_id, None)
            self.log_exception(
                "Mention %s thất bại %d lần, đánh dấu failed (chờ retry_failed thủ công)",
                mention_id,
                attempts,
            )
            try:
                await self.repo.mark_failed(mention_id, f"{type(exc).__name__}: {exc}")
            except Exception:
                self.log_exception("Không thể mark_failed mention %s", mention_id)
            return
        # Giữ status=pending, lên lịch tự re-enqueue sau retry_delay (sleep ở task
        # tách rời nên KHÔNG giữ slot semaphore suốt thời gian chờ).
        self.log_exception(
            "Enrich mention %s thất bại (lần %d/%d) — thử lại sau %.0fs",
            mention_id,
            attempts,
            self.max_attempts,
            self.retry_delay,
        )
        self._schedule_retry(mention_id)

    def _schedule_retry(self, mention_id: str) -> None:
        if self._stopping:
            return
        task = asyncio.create_task(self._retry_after_delay(mention_id))
        self._retry_tasks.add(task)
        task.add_done_callback(self._retry_tasks.discard)

    async def _retry_after_delay(self, mention_id: str) -> None:
        try:
            await asyncio.sleep(self.retry_delay)
        except asyncio.CancelledError:
            return
        if not self._stopping:
            self.enqueue(mention_id)

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
