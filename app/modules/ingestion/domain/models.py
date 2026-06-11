from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.core.model import BaseMongoModel


class MentionStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Mention(BaseMongoModel):
    subject: str | None = None
    source: str | None = None
    platform: str | None = None  # nền tảng suy ra từ url: Facebook, TikTok, Instagram, Threads...
    author: str | None = None
    url: str | None = None
    mention: str
    received_at: datetime | None = None
    kompa_analysis: str | None = None
    has_ai_analysis: bool | None = None
    status: MentionStatus = MentionStatus.PENDING
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    failed_reason: str | None = None
    bi_enriched_at: datetime | None = None
    bi_topic: str | None = None
    bi_product_area: str | None = None
    bi_severity: int | None = None
    bi_intent: str | None = None
    bi_is_actionable: bool | None = None
    bi_summary_vi: str | None = None

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)
