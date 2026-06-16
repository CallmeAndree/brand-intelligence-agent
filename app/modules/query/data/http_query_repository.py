"""Impl HTTP của QueryRepo — gọi data-backend facade /repo/find|aggregate (REPO_MODE=http).

Body/response qua Extended JSON (bson.json_util) để giữ kiểu Date/ObjectId qua HTTP
(giống HttpReader) — relaxed JSON sẽ biến Date thành string làm hỏng range thời gian.
"""

from typing import Any

import httpx
from bson import json_util

from app.modules.query.domain.repository import QueryRepo


class HttpQueryRepository(QueryRepo):
    def __init__(self, base_url: str, token: str, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Data-Token": token},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, spec: dict) -> list[dict[str, Any]]:
        resp = await self._client.post(
            path,
            content=json_util.dumps(spec),
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return list(json_util.loads(resp.text))

    async def find(
        self,
        collection: str,
        filter: dict[str, Any],
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
        projection: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        spec: dict[str, Any] = {"collection": collection, "filter": filter}
        if sort:
            spec["sort"] = dict(sort)
        if limit:
            spec["limit"] = limit
        if projection:
            spec["projection"] = projection
        return await self._post("/repo/find", spec)

    async def aggregate(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return await self._post(
            "/repo/aggregate", {"collection": collection, "pipeline": pipeline}
        )

    async def find_one(
        self, collection: str, filter: dict[str, Any]
    ) -> dict[str, Any] | None:
        docs = await self.find(collection, filter, limit=1)
        return docs[0] if docs else None
