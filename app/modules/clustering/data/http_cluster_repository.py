"""Impl HTTP của ClusterRepo — qua data-backend facade (REPO_MODE=http).

Cho phép online incremental clustering chạy CẢ trên runtime PUBLIC (deploy) nơi
không nối Mongo trực tiếp: đọc/ghi `topic_cluster`/`keyword_groups` + `$set` field
cụm về `mentions` qua `/repo/find` và `/repo/update-one` (upsert). EJSON giữ kiểu
Date/centroid qua HTTP. Mirror HttpAlertRepository.
"""

import httpx
from bson import json_util

from app.core.logging_mixin import LoggerMixin
from app.modules.clustering.domain.models import Cluster, KeywordGroup
from app.modules.clustering.domain.repository import ClusterRepo

_CLUSTERS = "topic_cluster"
_KEYWORD_GROUPS = "keyword_groups"
_MENTIONS = "mentions"


class HttpClusterRepository(ClusterRepo, LoggerMixin):
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Data-Token": token},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, spec: dict) -> str:
        resp = await self._client.post(
            path,
            content=json_util.dumps(spec),
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.text

    async def ensure_indexes(self) -> None:
        return None  # index tạo phía data-backend

    async def load_clusters(self) -> list[Cluster]:
        text = await self._post(
            "/repo/find",
            {"collection": _CLUSTERS, "filter": {"centroid": {"$exists": True, "$type": "array"}}},
        )
        return [Cluster.model_validate(doc) for doc in json_util.loads(text)]

    async def load_keyword_groups(self) -> list[KeywordGroup]:
        text = await self._post("/repo/find", {"collection": _KEYWORD_GROUPS, "filter": {}})
        return [KeywordGroup.model_validate(doc) for doc in json_util.loads(text)]

    async def upsert_cluster(self, cluster: Cluster) -> None:
        await self._post(
            "/repo/update-one",
            {
                "collection": _CLUSTERS,
                "filter": {"_id": cluster.id},
                "update": {"$set": cluster.to_mongo()},
                "upsert": True,
            },
        )

    async def upsert_keyword_group(self, group: KeywordGroup) -> None:
        await self._post(
            "/repo/update-one",
            {
                "collection": _KEYWORD_GROUPS,
                "filter": {"_id": group.id},
                "update": {"$set": group.to_mongo()},
                "upsert": True,
            },
        )

    async def set_mention_clustering(
        self,
        mention_id: str,
        cluster_id: int,
        cluster_label: str,
        keyword_group_ids: list[int],
    ) -> None:
        await self._post(
            "/repo/update-one",
            {
                "collection": _MENTIONS,
                "filter": {"_id": mention_id},
                "update": {
                    "$set": {
                        "cluster_id": cluster_id,
                        "cluster_label": cluster_label,
                        "keyword_group_ids": keyword_group_ids,
                    }
                },
            },
        )
