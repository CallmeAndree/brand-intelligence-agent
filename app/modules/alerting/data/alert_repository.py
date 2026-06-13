"""Impl Mongo của AlertRepository (REPO_MODE=mongo)."""

from datetime import datetime

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.modules.alerting.domain.models import Alert
from app.modules.alerting.domain.repository import AlertRepository


class MongoAlertRepository(AlertRepository):
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db["alerts"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("created_at", DESCENDING)])
        await self.collection.create_index([("cluster_id", ASCENDING)])

    async def insert(self, alert: Alert) -> None:
        await self.collection.replace_one({"_id": alert.id}, alert.to_mongo(), upsert=True)

    async def find_recent(self, limit: int = 50, since: str | None = None) -> list[Alert]:
        query: dict = {}
        if since:
            query["created_at"] = {"$gte": datetime.fromisoformat(since)}
        cursor = self.collection.find(query).sort([("created_at", DESCENDING)]).limit(limit)
        return [Alert.model_validate(doc) async for doc in cursor]
