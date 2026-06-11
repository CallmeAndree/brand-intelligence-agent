from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.ingestion.domain.models import Mention
from app.modules.ingestion.domain.platform import platform_from_url


class IngestEmailRequest(BaseModel):
    id: str = Field(alias="_id")
    subject: str | None = None
    source: str | None = None
    author: str | None = None
    url: str | None = None
    mention: str
    received_at: datetime | None = None
    ai_analysis: str | None = None
    has_ai_analysis: bool | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @field_validator("id", "mention")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if value is None or not str(value).strip():
            raise ValueError("must be non-empty")
        return str(value).strip()

    @field_validator("received_at", mode="before")
    @classmethod
    def parse_received_at(cls, value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        return value

    def to_domain(self) -> Mention:
        return Mention(
            _id=self.id,
            subject=self.subject,
            source=self.source,
            author=self.author,
            url=self.url,
            platform=platform_from_url(self.url),
            mention=self.mention,
            received_at=self.received_at,
            kompa_analysis=self.ai_analysis,
            has_ai_analysis=self.has_ai_analysis,
            ingested_at=datetime.now(timezone.utc),
        )


class IngestEmailResponse(BaseModel):
    id: str = Field(alias="_id")
    status: str

    model_config = ConfigDict(populate_by_name=True)
