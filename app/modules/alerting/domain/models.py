"""Domain models module alerting (manual alert cho một cụm)."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.model import BaseMongoModel, make_prefixed_id


class EmailStatus(StrEnum):
    SENT = "sent"
    SKIPPED = "skipped"  # thiếu cấu hình SMTP
    FAILED = "failed"


class Department(BaseModel):
    """Phòng ban đích của alert (tên + mô tả ngắn)."""

    name: str
    rationale: str | None = None


class AlertEmail(BaseModel):
    to: str | None = None
    subject: str | None = None
    status: EmailStatus = EmailStatus.SKIPPED
    error: str | None = None
    sent_at: datetime | None = None


class Alert(BaseMongoModel):
    kind: str = "manual"
    cluster_id: int
    department: str
    severity_snapshot: int | None = None
    brief_md: str
    email: AlertEmail = Field(default_factory=AlertEmail)
    source_mention_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    @staticmethod
    def new_id() -> str:
        return make_prefixed_id("alert")

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)
