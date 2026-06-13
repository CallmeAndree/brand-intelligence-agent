"""Repository hướng HTTP — implementation thứ 2 của MentionRepo.

Dùng khi agent chạy ở runtime PUBLIC (AgentBase) không chạm Mongo trực tiếp được.
Mọi thao tác đọc/ghi được gửi tới `data-backend` (FastAPI trên VM, cạnh Mongo),
qua Cloudflare tunnel. Logic nghiệp vụ (save_partial/mark_enriched/mark_failed
$set) vẫn nằm DUY NHẤT ở MentionDataRepository phía backend — repo này chỉ chuyển vận.
"""

import httpx

from app.core.logging_mixin import LoggerMixin
from app.modules.ingestion.domain.models import Mention
from app.modules.ingestion.domain.repository import MentionRepo


class HttpMentionRepository(MentionRepo, LoggerMixin):
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Data-Token": token},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ensure_indexes(self) -> None:
        resp = await self._client.post("/repo/ensure-indexes")
        resp.raise_for_status()

    async def upsert(self, mention: Mention) -> None:
        payload = mention.model_dump(by_alias=True, exclude_none=True, mode="json")
        resp = await self._client.post("/repo/upsert", json=payload)
        resp.raise_for_status()

    async def get(self, mention_id: str) -> Mention | None:
        resp = await self._client.get(f"/repo/get/{mention_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return Mention.model_validate(resp.json())

    async def find_pending_ids(self) -> list[str]:
        resp = await self._client.get("/repo/pending-ids")
        resp.raise_for_status()
        return resp.json()["ids"]

    async def find_failed_ids(self) -> list[str]:
        resp = await self._client.get("/repo/failed-ids")
        resp.raise_for_status()
        return resp.json()["ids"]

    async def save_partial(self, mention_id: str, values: dict) -> None:
        resp = await self._client.post(
            f"/repo/save-partial/{mention_id}",
            json=values,
        )
        resp.raise_for_status()

    async def mark_enriched(self, mention_id: str) -> None:
        resp = await self._client.post(f"/repo/mark-enriched/{mention_id}")
        resp.raise_for_status()

    async def mark_failed(self, mention_id: str, reason: str) -> None:
        resp = await self._client.post(
            f"/repo/mark-failed/{mention_id}",
            json={"reason": reason},
        )
        resp.raise_for_status()
