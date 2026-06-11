from datetime import datetime, timezone

from pymongo import ASCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.modules.enrichment.domain.models import BiFields
from app.modules.ingestion.domain.models import Mention, MentionStatus
from app.modules.ingestion.domain.repository import MentionRepo


class MentionDataRepository(MentionRepo):
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db["mentions"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("status", ASCENDING)])
        await self.collection.create_index([("received_at", ASCENDING)])

    async def upsert(self, mention: Mention) -> None:
        await self.collection.replace_one(
            {"_id": mention.id},
            mention.to_mongo(),
            upsert=True,
        )

    async def get(self, mention_id: str) -> Mention | None:
        document = await self.collection.find_one({"_id": mention_id})
        if document is None:
            return None
        return Mention.model_validate(document)

    async def find_pending_ids(self) -> list[str]:
        cursor = self.collection.find({"status": MentionStatus.PENDING.value}, {"_id": 1})
        return [doc["_id"] async for doc in cursor]

    async def find_failed_ids(self) -> list[str]:
        cursor = self.collection.find({"status": MentionStatus.FAILED.value}, {"_id": 1})
        return [doc["_id"] async for doc in cursor]

    async def set_enrichment(self, mention_id: str, fields: BiFields) -> None:
        values = fields.model_dump()
        values["bi_enriched_at"] = datetime.now(timezone.utc)
        values["status"] = MentionStatus.DONE.value
        values["failed_reason"] = None
        await self.collection.update_one({"_id": mention_id}, {"$set": values})

    async def mark_failed(self, mention_id: str, reason: str) -> None:
        await self.collection.update_one(
            {"_id": mention_id},
            {
                "$set": {
                    "status": MentionStatus.FAILED.value,
                    "failed_reason": reason[:2000],
                },
                "$unset": {
                    "bi_topic": "",
                    "bi_product_area": "",
                    "bi_keywords": "",
                    "bi_severity": "",
                    "bi_intent": "",
                    "bi_is_actionable": "",
                    "bi_summary_vi": "",
                    "bi_enriched_at": "",
                },
            },
        )
