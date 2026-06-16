"""Impl Mongo trực tiếp của QueryRepo (REPO_MODE=mongo)."""

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.modules.query.domain.repository import QueryRepo


class MongoQueryRepository(QueryRepo):
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db

    async def find(
        self,
        collection: str,
        filter: dict[str, Any],
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
        projection: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._db[collection].find(filter, projection or None)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return [doc async for doc in cursor]

    async def aggregate(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [doc async for doc in await self._db[collection].aggregate(pipeline)]

    async def find_one(
        self, collection: str, filter: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self._db[collection].find_one(filter)
