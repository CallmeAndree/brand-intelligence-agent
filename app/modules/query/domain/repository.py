"""ABC cho data access của tool catalog — 2 impl (Mongo trực tiếp / HTTP facade).

Use case build filter/pipeline THUẦN rồi gọi repo; repo chỉ thực thi đọc (find/
aggregate/find_one), không build logic. Khớp REPO_MODE giống MentionRepo/Reader.
"""

from abc import ABC, abstractmethod
from typing import Any


class QueryRepo(ABC):
    @abstractmethod
    async def find(
        self,
        collection: str,
        filter: dict[str, Any],
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
        projection: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def aggregate(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def find_one(
        self, collection: str, filter: dict[str, Any]
    ) -> dict[str, Any] | None:
        raise NotImplementedError
