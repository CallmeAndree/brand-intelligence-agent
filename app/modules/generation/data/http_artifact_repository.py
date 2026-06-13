"""Impl HTTP của MonitorArtifactRepo — gọi data-backend facade (REPO_MODE=http).

Dùng khi Runtime 1 chạy PUBLIC không chạm Mongo trực tiếp. Body/response qua
Extended JSON (bson.json_util) để giữ kiểu Date/ObjectId — giống các route đọc.
"""

import json

import httpx
from bson import json_util

from app.core.logging_mixin import LoggerMixin
from app.modules.generation.domain.models import ArtifactStatus, MonitorArtifact
from app.modules.generation.domain.repository import MonitorArtifactRepo

_COLLECTION = "monitor_artifacts"


class HttpMonitorArtifactRepository(MonitorArtifactRepo, LoggerMixin):
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Data-Token": token},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post_ejson(self, path: str, spec: dict) -> str:
        resp = await self._client.post(
            path,
            content=json_util.dumps(spec),
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.text

    async def ensure_indexes(self) -> None:
        # Index tạo phía data-backend (chạy cạnh Mongo). Runtime http bỏ qua an toàn.
        return None

    async def insert_draft(self, artifact: MonitorArtifact) -> None:
        await self._post_ejson(
            "/repo/insert-one", {"collection": _COLLECTION, "doc": artifact.to_mongo()}
        )

    async def find_by_cluster(self, cluster_id: int) -> list[MonitorArtifact]:
        text = await self._post_ejson(
            "/repo/find",
            {
                "collection": _COLLECTION,
                "filter": {"cluster_id": cluster_id, "status": {"$ne": "discarded"}},
                "sort": {"created_at": -1},
            },
        )
        docs = json_util.loads(text)
        return [MonitorArtifact.model_validate(doc) for doc in docs]

    async def set_status(self, artifact_id: str, status: ArtifactStatus) -> bool:
        text = await self._post_ejson(
            "/repo/update-one",
            {
                "collection": _COLLECTION,
                "filter": {"_id": artifact_id},
                "update": {"$set": {"status": status.value}},
            },
        )
        return json.loads(text).get("matched_count", 0) > 0
