"""5 use case sinh nội dung AI cho một cụm (monitor workspace).

Mỗi use case `@dataclass(frozen=True)` nhận `llm` + text playbook đã load (DI ở
main.py qua `load_prompt`) + tên model/file để truy vết.

Sinh **text Markdown thuần** (không structured JSON) — xem `core.text_gen`: đầy
đủ hơn + nhanh hơn + stream được. Mỗi use case có 3 cách dùng:
- `stream(ctx)`  → async-iter từng delta (SSE realtime).
- `execute(ctx)` → 1 call, trả `MonitorArtifact` (fallback non-stream).
- `build(ctx, content_md)` → đóng gói text đã có thành `MonitorArtifact`.

Ngữ cảnh vấn đề của cụm LUÔN được nhét vào prompt qua `ClusterContext.to_prompt_block()`
(nhãn cụm + chủ đề + nhóm từ khóa + mention tiêu biểu) để MINIMAX bám sát dẫn chứng.
Ràng buộc thương hiệu (CHỈ ZaloPay/ZLP) nằm trong playbook `.md` + persona dưới đây.
"""

from dataclasses import dataclass
from typing import Any, AsyncIterator

from agent_framework import Message

from app.core.text_gen import complete_text, stream_text
from app.modules.generation.domain.models import (
    ArtifactType,
    ArtifactVariant,
    ClusterContext,
    ModelMeta,
    MonitorArtifact,
)

_BRAND_PERSONA = (
    "Bạn là chuyên gia phân tích thương hiệu & xử lý khủng hoảng truyền thông của "
    "ZaloPay (ZLP) — ví điện tử thuộc VNG. CHỈ về ZaloPay, KHÔNG bao gồm Zalo (app "
    "chat là sản phẩm khác). Mọi mention đều là phản hồi tiêu cực về ZaloPay. "
    "Trả lời bằng tiếng Việt, viết ĐẦY ĐỦ nội dung từng mục (KHÔNG rút gọn thành "
    "tiêu đề), định dạng Markdown sạch: heading `##`/`###`, bullet `-`, in đậm "
    "`**...**`, cách dòng trống giữa các đoạn để dễ đọc."
)


def _user_message(prompt: str, ctx: ClusterContext) -> Message:
    return Message(
        "user",
        [
            f"{prompt}\n\n## Ngữ cảnh vấn đề của cụm (bám sát dữ liệu này)\n"
            f"{ctx.to_prompt_block()}"
        ],
    )


@dataclass(frozen=True)
class _BaseContentUseCase:
    """Khung dùng chung cho 4 use case trả 1 khối content_md (narrative, root_cause,
    response_strategy, seeding_comments)."""

    llm: Any
    prompt: str
    prompt_file: str
    model_name: str
    artifact_type: ArtifactType

    def _messages(self, ctx: ClusterContext) -> list[Message]:
        return [Message("system", [_BRAND_PERSONA]), _user_message(self.prompt, ctx)]

    async def stream(self, ctx: ClusterContext) -> AsyncIterator[str]:
        async for delta in stream_text(self.llm, self._messages(ctx)):
            yield delta

    async def execute(self, ctx: ClusterContext) -> MonitorArtifact:
        content_md = await complete_text(self.llm, self._messages(ctx))
        return self.build(ctx, content_md)

    def build(self, ctx: ClusterContext, content_md: str) -> MonitorArtifact:
        return MonitorArtifact(
            _id=MonitorArtifact.new_id(),
            cluster_id=ctx.cluster_id,
            type=self.artifact_type,
            content_md=content_md.strip() or "(không sinh được nội dung)",
            model_meta=ModelMeta(model=self.model_name, prompt_file=self.prompt_file),
            source_mention_ids=[m.id for m in ctx.top_mentions],
        )


@dataclass(frozen=True)
class GenerateNarrativeUseCase(_BaseContentUseCase):
    pass


@dataclass(frozen=True)
class GenerateRootCauseUseCase(_BaseContentUseCase):
    pass


@dataclass(frozen=True)
class GenerateResponseStrategyUseCase(_BaseContentUseCase):
    pass


@dataclass(frozen=True)
class GenerateSeedingUseCase(_BaseContentUseCase):
    pass


def _parse_variants(content_md: str) -> list[ArtifactVariant]:
    """Tách markdown thành các variant theo heading `### {tone}`.

    Không có heading nào → coi toàn bộ là 1 variant. Giữ nguyên thân markdown.
    """
    variants: list[ArtifactVariant] = []
    label: str | None = None
    body: list[str] = []

    def flush() -> None:
        if label is not None:
            text = "\n".join(body).strip()
            if text:
                variants.append(ArtifactVariant(label=label, content_md=text))

    for line in content_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            flush()
            label = stripped[4:].strip().lstrip("#").strip() or "Phản hồi"
            body = []
        elif label is not None:
            body.append(line)
    flush()

    if not variants:
        text = content_md.strip()
        if text:
            variants.append(ArtifactVariant(label="Phản hồi", content_md=text))
    return variants


@dataclass(frozen=True)
class GenerateBrandVoiceUseCase:
    """Sinh nhiều variant tone trong 1 lần — đọc thêm playbook tone.

    Stream markdown thuần với các mục `### {tone}`; khi xong tách thành variants
    cho UI hiển thị tab. content_md giữ toàn bộ markdown để render fallback.
    """

    llm: Any
    prompt: str
    tone_prompt: str
    prompt_file: str
    model_name: str
    artifact_type: ArtifactType = ArtifactType.BRAND_VOICE

    def _messages(self, ctx: ClusterContext) -> list[Message]:
        combined = (
            f"{self.prompt}\n\n## Hướng dẫn giọng điệu (tone)\n{self.tone_prompt}\n\n"
            "QUAN TRỌNG: Mỗi tone là một mục bắt đầu bằng heading `### <tên tone>`, "
            "tiếp theo là nội dung phản hồi hoàn chỉnh cho tone đó. Tạo tối thiểu 3 tone."
        )
        return [Message("system", [_BRAND_PERSONA]), _user_message(combined, ctx)]

    async def stream(self, ctx: ClusterContext) -> AsyncIterator[str]:
        async for delta in stream_text(self.llm, self._messages(ctx)):
            yield delta

    async def execute(self, ctx: ClusterContext) -> MonitorArtifact:
        content_md = await complete_text(self.llm, self._messages(ctx))
        return self.build(ctx, content_md)

    def build(self, ctx: ClusterContext, content_md: str) -> MonitorArtifact:
        variants = _parse_variants(content_md)
        return MonitorArtifact(
            _id=MonitorArtifact.new_id(),
            cluster_id=ctx.cluster_id,
            type=ArtifactType.BRAND_VOICE,
            content_md=content_md.strip() or "(không sinh được nội dung)",
            variants=variants,
            model_meta=ModelMeta(model=self.model_name, prompt_file=self.prompt_file),
            source_mention_ids=[m.id for m in ctx.top_mentions],
        )
