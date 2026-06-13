"""Reader đọc Mongo dùng chung cho generation/alerting (build ngữ cảnh cụm).

Hai impl khớp REPO_MODE: `MongoReader` (PyMongo trực tiếp) và `HttpReader` (qua
data-backend facade /repo/find|aggregate, EJSON). Giữ logic build context thuần,
không phụ thuộc transport.
"""

from typing import Any, Protocol

import httpx
from bson import json_util
from pymongo.asynchronous.database import AsyncDatabase


class Reader(Protocol):
    async def find(
        self,
        collection: str,
        filter: dict[str, Any],
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]: ...

    async def find_one(
        self, collection: str, filter: dict[str, Any]
    ) -> dict[str, Any] | None: ...


class MongoReader:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db

    async def find(
        self,
        collection: str,
        filter: dict[str, Any],
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._db[collection].find(filter)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return [doc async for doc in cursor]

    async def find_one(
        self, collection: str, filter: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self._db[collection].find_one(filter)


class HttpReader:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Data-Token": token},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def find(
        self,
        collection: str,
        filter: dict[str, Any],
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        spec: dict[str, Any] = {"collection": collection, "filter": filter}
        if sort:
            spec["sort"] = dict(sort)
        if limit:
            spec["limit"] = limit
        resp = await self._client.post(
            "/repo/find",
            content=json_util.dumps(spec),
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return list(json_util.loads(resp.text))

    async def find_one(
        self, collection: str, filter: dict[str, Any]
    ) -> dict[str, Any] | None:
        docs = await self.find(collection, filter, limit=1)
        return docs[0] if docs else None
