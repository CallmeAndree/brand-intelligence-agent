"""Impl HTTP của AlertRepository — qua data-backend facade (REPO_MODE=http)."""

import httpx
from bson import json_util

from app.core.logging_mixin import LoggerMixin
from app.modules.alerting.domain.models import Alert
from app.modules.alerting.domain.repository import AlertRepository

_COLLECTION = "alerts"


class HttpAlertRepository(AlertRepository, LoggerMixin):
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
        return None  # index tạo phía data-backend

    async def insert(self, alert: Alert) -> None:
        await self._post_ejson(
            "/repo/insert-one", {"collection": _COLLECTION, "doc": alert.to_mongo()}
        )

    async def find_recent(self, limit: int = 50, since: str | None = None) -> list[Alert]:
        from datetime import datetime

        query: dict = {}
        if since:
            query["created_at"] = {"$gte": datetime.fromisoformat(since)}
        text = await self._post_ejson(
            "/repo/find",
            {
                "collection": _COLLECTION,
                "filter": query,
                "sort": {"created_at": -1},
                "limit": limit,
            },
        )
        return [Alert.model_validate(doc) for doc in json_util.loads(text)]

    async def ack(self, alert_id: str) -> bool:
        from datetime import datetime, timezone

        text = await self._post_ejson(
            "/repo/update-one",
            {
                "collection": _COLLECTION,
                "filter": {"_id": alert_id},
                "update": {
                    "$set": {
                        "acknowledged": True,
                        "acknowledged_at": datetime.now(timezone.utc),
                    }
                },
            },
        )
        result = json_util.loads(text)
        return int(result.get("modified_count", 0)) > 0
