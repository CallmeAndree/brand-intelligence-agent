from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.modules.ingestion.domain.models import Mention, MentionStatus
from app.modules.ingestion.domain.repository import MentionRepo

EnqueueFn = Callable[[str], Awaitable[None] | None]


@dataclass(frozen=True)
class IngestEmailUseCase:
    repo: MentionRepo
    enqueue: EnqueueFn

    async def execute(self, mention: Mention) -> Mention:
        mention.status = MentionStatus.PENDING
        await self.repo.upsert(mention)
        result = self.enqueue(mention.id)
        if result is not None:
            await result
        return mention
