from abc import ABC, abstractmethod
from typing import Any

from app.modules.ingestion.domain.models import Mention


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
    async def save_partial(self, mention_id: str, values: dict[str, Any]) -> None:
        """Ghi tăng dần một phần kết quả enrich (1 pass / embedding) — KHÔNG đổi
        status (vẫn pending). Gọi được pass nào lưu pass đó để retry resume được."""
        raise NotImplementedError

    @abstractmethod
    async def mark_enriched(self, mention_id: str) -> None:
        """Chốt enrich: lật status=done sau khi mọi pass + embedding đã save_partial."""
        raise NotImplementedError

    @abstractmethod
    async def mark_failed(self, mention_id: str, reason: str) -> None:
        raise NotImplementedError
