from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from app.modules.ingestion.domain.models import Mention

if TYPE_CHECKING:
    from app.modules.enrichment.domain.models import BiFields


class MentionRepo(ABC):
    @abstractmethod
    async def ensure_indexes(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, mention: Mention) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, mention_id: str) -> Mention | None:
        raise NotImplementedError

    @abstractmethod
    async def find_pending_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def find_failed_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def set_enrichment(self, mention_id: str, fields: "BiFields") -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_failed(self, mention_id: str, reason: str) -> None:
        raise NotImplementedError
