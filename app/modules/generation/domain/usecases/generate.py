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
Ràng buộc thương hiệu (CHỈ Zalopay/ZLP) nằm trong playbook `.md` + persona dưới đây.
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
    "Zalopay (ZLP) — ví điện tử thuộc VNG. CHỈ về Zalopay, KHÔNG bao gồm Zalo (app "
    "chat là sản phẩm khác). Mọi mention đều là phản hồi tiêu cực về Zalopay. "
    "CHÍNH TẢ THƯƠNG HIỆU BẮT BUỘC: luôn viết đúng 'Zalopay' (Z hoa, còn lại "
    "thường liền nhau) — TUYỆT ĐỐI KHÔNG viết 'ZaloPay', 'Zalo Pay', 'zalopay' "
    "hay 'ZALOPAY' trong mọi nội dung sinh ra (kể cả draft/comment/email). "
    "Trả lời bằng tiếng Việt. MẶC ĐỊNH viết đầy đủ nội dung từng mục, định dạng "
    "Markdown sạch (heading `##`/`###`, bullet `-`, in đậm `**...**`, cách dòng "
    "giữa các đoạn). Các quy ước hình thức này chỉ là GỢI Ý: nếu yêu cầu của người "
    "dùng mâu thuẫn (độ dài, cấu trúc, có/không heading, văn phong) thì LÀM THEO "
    "người dùng. Ràng buộc cứng duy nhất: phạm vi thương hiệu Zalopay/ZLP."
)


def _user_message(prompt: str, ctx: ClusterContext, instruction: str = "") -> Message:
    parts = [
        f"{prompt}\n\n## Ngữ cảnh vấn đề của cụm (bám sát dữ liệu này)\n"
        f"{ctx.to_prompt_block()}"
    ]
    instruction = (instruction or "").strip()
    if instruction:
        # Yêu cầu người dùng đặt CUỐI + ưu tiên tuyệt đối: ghi đè quy ước hình thức
        # mặc định ở playbook/persona nếu mâu thuẫn (vd "ngắn gọn", "không heading").
        parts.append(
            "## Yêu cầu BẮT BUỘC từ người dùng (ưu tiên TUYỆT ĐỐI)\n"
            f"{instruction}\n\n"
            "Phải tuân thủ yêu cầu này; nếu mâu thuẫn với hướng dẫn mặc định phía trên "
            "(độ dài, mức chi tiết, văn phong, cấu trúc) thì LÀM THEO yêu cầu này."
        )
    return Message("user", ["\n\n".join(parts)])


@dataclass(frozen=True)
class _BaseContentUseCase:
    """Khung dùng chung cho 4 use case trả 1 khối content_md (narrative, root_cause,
    response_strategy, seeding_comments)."""

    llm: Any
    prompt: str
    prompt_file: str
    model_name: str
    artifact_type: ArtifactType

    def _messages(self, ctx: ClusterContext, instruction: str = "") -> list[Message]:
        return [Message("system", [_BRAND_PERSONA]), _user_message(self.prompt, ctx, instruction)]

    async def stream(self, ctx: ClusterContext, instruction: str = "") -> AsyncIterator[str]:
        async for delta in stream_text(self.llm, self._messages(ctx, instruction)):
            yield delta

    async def execute(self, ctx: ClusterContext, instruction: str = "") -> MonitorArtifact:
        content_md = await complete_text(self.llm, self._messages(ctx, instruction))
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
    """Seeding theo nhiều giọng điệu (Guide / Counter / Protect) — comment ngắn, slang, Gen Z.

    Giống brand voice: LLM xuất các mục `### <tone>`; `build` tách `_parse_variants`
    để UI hiện tab tone. `content_md` giữ toàn bộ markdown làm fallback render.
    """

    def build(self, ctx: ClusterContext, content_md: str) -> MonitorArtifact:
        variants = _parse_variants(content_md)
        return MonitorArtifact(
            _id=MonitorArtifact.new_id(),
            cluster_id=ctx.cluster_id,
            type=self.artifact_type,
            content_md=content_md.strip() or "(không sinh được nội dung)",
            variants=variants,
            model_meta=ModelMeta(model=self.model_name, prompt_file=self.prompt_file),
            source_mention_ids=[m.id for m in ctx.top_mentions],
        )


@dataclass(frozen=True)
class _ContextContentUseCase:
    """Khung cho 3 skill sinh nội dung TỪ CHAT (content/design_brief/response_plan).

    Khác `_BaseContentUseCase`: nhận **ngữ cảnh tự do `context: str`** (artifact đã
    inject từ Monitor / mô tả người dùng / ClusterContext do RT1 dựng sẵn) thay vì
    bắt buộc một `ClusterContext`. `build` đóng gói thành `MonitorArtifact` với
    `created_by="chat"` + `session_id` (artifact chat không bắt buộc gắn cụm).
    """

    llm: Any
    prompt: str
    prompt_file: str
    model_name: str
    artifact_type: ArtifactType

    def _messages(self, context: str, instruction: str = "") -> list[Message]:
        ctx_block = context.strip() or "(không có ngữ cảnh bổ sung — dựa trên yêu cầu chung)"
        parts = [self.prompt, f"## Ngữ cảnh (bám sát dữ liệu này)\n{ctx_block}"]
        instruction = (instruction or "").strip()
        if instruction:
            # Yêu cầu người dùng đặt CUỐI + ưu tiên tuyệt đối: được phép ghi đè hướng dẫn
            # mặc định (độ dài, văn phong, cấu trúc) ở playbook/persona nếu mâu thuẫn.
            parts.append(
                "## Yêu cầu BẮT BUỘC từ người dùng (ưu tiên TUYỆT ĐỐI)\n"
                f"{instruction}\n\n"
                "Phải tuân thủ yêu cầu này. Nếu nó mâu thuẫn với hướng dẫn mặc định phía "
                "trên (ví dụ độ dài, mức chi tiết, văn phong, cấu trúc) thì LÀM THEO yêu "
                "cầu này — ví dụ yêu cầu 'ngắn gọn' thì viết ngắn gọn, không bung đủ mục."
            )
        return [Message("system", [_BRAND_PERSONA]), Message("user", ["\n\n".join(parts)])]

    async def stream(self, context: str, instruction: str = "") -> AsyncIterator[str]:
        async for delta in stream_text(self.llm, self._messages(context, instruction)):
            yield delta

    async def execute(
        self,
        context: str,
        *,
        instruction: str = "",
        cluster_id: int | None = None,
        session_id: str | None = None,
    ) -> MonitorArtifact:
        content_md = await complete_text(self.llm, self._messages(context, instruction))
        return self.build(content_md, cluster_id=cluster_id, session_id=session_id)

    def build(
        self, content_md: str, *, cluster_id: int | None = None, session_id: str | None = None
    ) -> MonitorArtifact:
        return MonitorArtifact(
            _id=MonitorArtifact.new_id(),
            cluster_id=cluster_id,
            type=self.artifact_type,
            content_md=content_md.strip() or "(không sinh được nội dung)",
            model_meta=ModelMeta(model=self.model_name, prompt_file=self.prompt_file),
            session_id=session_id,
            created_by="chat",
        )


@dataclass(frozen=True)
class GenerateContentUseCase(_ContextContentUseCase):
    pass


@dataclass(frozen=True)
class GenerateDesignBriefUseCase(_ContextContentUseCase):
    pass


@dataclass(frozen=True)
class GenerateResponsePlanUseCase(_ContextContentUseCase):
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

    def _messages(self, ctx: ClusterContext, instruction: str = "") -> list[Message]:
        combined = (
            f"{self.prompt}\n\n## Hướng dẫn giọng điệu (tone)\n{self.tone_prompt}\n\n"
            "QUAN TRỌNG: Mỗi tone là một mục bắt đầu bằng heading `### <tên tone>`, "
            "tiếp theo là nội dung phản hồi hoàn chỉnh cho tone đó. Tạo tối thiểu 3 tone."
        )
        return [Message("system", [_BRAND_PERSONA]), _user_message(combined, ctx, instruction)]

    async def stream(self, ctx: ClusterContext, instruction: str = "") -> AsyncIterator[str]:
        async for delta in stream_text(self.llm, self._messages(ctx, instruction)):
            yield delta

    async def execute(self, ctx: ClusterContext, instruction: str = "") -> MonitorArtifact:
        content_md = await complete_text(self.llm, self._messages(ctx, instruction))
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


# ---- Revise 5 nội dung Monitor TỪ CHAT (add-monitor-skill-followup) ----
# Khi "Gửi sang Chat" một artifact Monitor, follow-up revise đi qua đường sinh-từ-chat
# (ngữ cảnh tự do `context` + `instruction`) y như 3 skill chat, nhưng dùng ĐÚNG playbook
# Monitor tương ứng. Khác đường Monitor workspace: KHÔNG bắt buộc `ClusterContext` đầy đủ —
# nội dung gốc cần sửa đã nằm trong `context` (ghim từ RT2). Có `cluster_id` thì route vẫn
# dựng ClusterContext + chèn block lên đầu `context` (bám dẫn chứng cụm nếu còn dữ liệu).


@dataclass(frozen=True)
class _VariantContextUseCase(_ContextContentUseCase):
    """Revise-từ-chat cho brand_voice/seeding_comments — giữ variant tone `### <tone>`.

    Như use case Monitor gốc: tách `_parse_variants(content_md)` cho UI hiện tab tone;
    `content_md` giữ toàn bộ markdown làm fallback. Không heading `###` → 1 variant duy nhất.
    """

    def build(
        self, content_md: str, *, cluster_id: int | None = None, session_id: str | None = None
    ) -> MonitorArtifact:
        return MonitorArtifact(
            _id=MonitorArtifact.new_id(),
            cluster_id=cluster_id,
            type=self.artifact_type,
            content_md=content_md.strip() or "(không sinh được nội dung)",
            variants=_parse_variants(content_md),
            model_meta=ModelMeta(model=self.model_name, prompt_file=self.prompt_file),
            session_id=session_id,
            created_by="chat",
        )


@dataclass(frozen=True)
class ReviseNarrativeUseCase(_ContextContentUseCase):
    pass


@dataclass(frozen=True)
class ReviseRootCauseUseCase(_ContextContentUseCase):
    pass


@dataclass(frozen=True)
class ReviseResponseStrategyUseCase(_ContextContentUseCase):
    pass


@dataclass(frozen=True)
class ReviseBrandVoiceUseCase(_VariantContextUseCase):
    pass


@dataclass(frozen=True)
class ReviseSeedingUseCase(_VariantContextUseCase):
    pass
