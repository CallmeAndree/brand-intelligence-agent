"""Repository hướng HTTP — implementation thứ 2 của MentionRepo.

Dùng khi agent chạy ở runtime PUBLIC (AgentBase) không chạm Mongo trực tiếp được.
Mọi thao tác đọc/ghi được gửi tới `data-backend` (FastAPI trên VM, cạnh Mongo),
qua Cloudflare tunnel. Logic nghiệp vụ (set_enrichment/mark_failed $set/$unset)
vẫn nằm DUY NHẤT ở MentionDataRepository phía backend — repo này chỉ chuyển vận.
"""

import httpx

from app.core.logging_mixin import LoggerMixin
from app.modules.enrichment.domain.models import BiFields
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

    async def set_enrichment(self, mention_id: str, fields: BiFields) -> None:
        resp = await self._client.post(
            f"/repo/set-enrichment/{mention_id}",
            json=fields.model_dump(mode="json"),
        )
        resp.raise_for_status()

    async def mark_failed(self, mention_id: str, reason: str) -> None:
        resp = await self._client.post(
            f"/repo/mark-failed/{mention_id}",
            json={"reason": reason},
        )
        resp.raise_for_status()
