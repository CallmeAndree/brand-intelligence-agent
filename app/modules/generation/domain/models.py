"""Domain models cho module generation (monitor workspace).

- `MonitorArtifact`: nội dung AI sinh cho một cụm, lưu collection `monitor_artifacts`,
  vòng đời draft→approved/discarded, tham chiếu cụm qua `cluster_id` (KHÔNG nhúng
  nội dung mention vào cluster).
- `ClusterContext`: ngữ cảnh truyền vào use case sinh (cụm + top mention + keyword
  groups) — model thuần domain, KHÔNG persist.
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.model import BaseMongoModel, make_prefixed_id


class ArtifactType(StrEnum):
    NARRATIVE = "narrative"
    ROOT_CAUSE = "root_cause"
    RESPONSE_STRATEGY = "response_strategy"
    BRAND_VOICE = "brand_voice"
    SEEDING_COMMENTS = "seeding_comments"
    # 3 skill sinh nội dung TỪ CHAT (add-chat-tools-memory) — ngữ cảnh tự do.
    CONTENT = "content"
    DESIGN_BRIEF = "design_brief"
    RESPONSE_PLAN = "response_plan"


class ArtifactStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    DISCARDED = "discarded"


class ArtifactVariant(BaseModel):
    """Một biến thể (dùng cho brand_voice: mỗi tone là 1 variant có nhãn)."""

    label: str
    content_md: str


class ModelMeta(BaseModel):
    model: str
    prompt_file: str


class MonitorArtifact(BaseMongoModel):
    # cluster_id optional: artifact sinh từ chat (CONTENT/DESIGN_BRIEF/RESPONSE_PLAN)
    # có thể không gắn cụm nào (ngữ cảnh tự do). Artifact monitor vẫn luôn có cluster_id.
    cluster_id: int | None = None
    type: ArtifactType
    status: ArtifactStatus = ArtifactStatus.DRAFT
    content_md: str
    variants: list[ArtifactVariant] | None = None
    model_meta: ModelMeta
    source_mention_ids: list[str] = Field(default_factory=list)
    session_id: str | None = None
    # Nguồn tạo artifact: "monitor" (mặc định, từ workspace cụm) | "chat" (3 skill chat).
    created_by: str = "monitor"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    @staticmethod
    def new_id() -> str:
        return make_prefixed_id("art")

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class MentionRef(BaseModel):
    """Mention tóm tắt dùng làm dẫn chứng trong prompt (không nhúng full body)."""

    id: str
    summary: str | None = None
    severity: int | None = None
    intent: str | None = None
    product_area: str | None = None
    platform: str | None = None
    received_at: datetime | None = None
    url: str | None = None


class ClusterContext(BaseModel):
    cluster_id: int
    label: str
    count: int
    severity_max: int | None = None
    severity_avg: float | None = None
    sample_topics: list[str] = Field(default_factory=list)
    keyword_groups: list[str] = Field(default_factory=list)
    top_mentions: list[MentionRef] = Field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Render ngữ cảnh cụm thành text gọn cho prompt (top mention dạng bullet)."""
        lines = [
            f"- Nhãn cụm: {self.label}",
            f"- Số mention: {self.count}",
            f"- Severity (max/avg): {self.severity_max}/{self.severity_avg}",
        ]
        if self.sample_topics:
            lines.append("- Chủ đề mẫu: " + "; ".join(self.sample_topics[:8]))
        if self.keyword_groups:
            lines.append("- Nhóm từ khóa: " + "; ".join(self.keyword_groups[:10]))
        lines.append("- Mention tiêu biểu:")
        for m in self.top_mentions:
            day = m.received_at.date().isoformat() if m.received_at else "—"
            summary = m.summary or "(không có tóm tắt)"
            lines.append(
                f"  • [{day}] (sev {m.severity}, {m.intent or '—'}, {m.product_area or '—'}) {summary}"
            )
        return "\n".join(lines)
