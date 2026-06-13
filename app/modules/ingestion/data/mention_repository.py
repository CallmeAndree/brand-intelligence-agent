from datetime import datetime, timezone

from pymongo import ASCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.modules.ingestion.domain.models import Mention, MentionStatus
from app.modules.ingestion.domain.repository import MentionRepo


class MentionDataRepository(MentionRepo):
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db["mentions"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("status", ASCENDING)])
        await self.collection.create_index([("received_at", ASCENDING)])
        await self.collection.create_index([("cluster_id", ASCENDING)])
        await self.collection.create_index([("keyword_group_ids", ASCENDING)])
        await self.collection.create_index([("bi_product_area", ASCENDING)])
        await self.collection.create_index([("bi_intent", ASCENDING)])
        # Compound cho monitor workspace: liệt kê/sắp mention theo cụm trong khoảng ngày.
        await self.collection.create_index([("cluster_id", ASCENDING), ("received_at", ASCENDING)])

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

    async def save_partial(self, mention_id: str, values: dict) -> None:
        # Chỉ $set các trường truyền vào — KHÔNG đụng status (giữ pending) để
        # khi 429 ở pass sau, phần đã ghi vẫn còn cho lần retry resume.
        if not values:
            return
        await self.collection.update_one({"_id": mention_id}, {"$set": values})

    async def mark_enriched(self, mention_id: str) -> None:
        await self.collection.update_one(
            {"_id": mention_id},
            {
                "$set": {
                    "status": MentionStatus.DONE.value,
                    "bi_enriched_at": datetime.now(timezone.utc),
                    "failed_reason": None,
                }
            },
        )

    async def mark_failed(self, mention_id: str, reason: str) -> None:
        # Giữ nguyên các bi_* đã enrich được (gọi tới đâu lưu tới đó) — chỉ đánh dấu
        # failed + lý do. retry_failed re-enqueue sẽ resume từ pass còn thiếu.
        await self.collection.update_one(
            {"_id": mention_id},
            {
                "$set": {
                    "status": MentionStatus.FAILED.value,
                    "failed_reason": reason[:2000],
                }
            },
        )
