"""Impl Mongo trực tiếp của MonitorArtifactRepo (REPO_MODE=mongo)."""

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.modules.generation.domain.models import ArtifactStatus, MonitorArtifact
from app.modules.generation.domain.repository import MonitorArtifactRepo


class MongoMonitorArtifactRepository(MonitorArtifactRepo):
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db["monitor_artifacts"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("cluster_id", ASCENDING), ("type", ASCENDING)])
        await self.collection.create_index([("session_id", ASCENDING)])

    async def insert_draft(self, artifact: MonitorArtifact) -> None:
        await self.collection.replace_one(
            {"_id": artifact.id}, artifact.to_mongo(), upsert=True
        )

    async def find_by_cluster(self, cluster_id: int) -> list[MonitorArtifact]:
        cursor = self.collection.find(
            {"cluster_id": cluster_id, "status": {"$ne": "discarded"}}
        ).sort([("created_at", DESCENDING)])
        return [MonitorArtifact.model_validate(doc) async for doc in cursor]

    async def set_status(self, artifact_id: str, status: ArtifactStatus) -> bool:
        result = await self.collection.update_one(
            {"_id": artifact_id}, {"$set": {"status": status.value}}
        )
        return result.matched_count > 0
