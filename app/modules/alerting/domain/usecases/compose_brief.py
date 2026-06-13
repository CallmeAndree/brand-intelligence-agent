"""ComposeBriefUseCase — sinh brief alert bằng LLM (playbook alert/alert_brief.md).

Brief vốn chỉ là một khối Markdown → sinh **text thuần** (`core.text_gen`) thay vì
structured JSON: nhanh hơn (1 call, không fallback) → rút ngắn thời gian phát alert.
"""

from dataclasses import dataclass
from typing import Any

from agent_framework import Message

from app.core.text_gen import complete_text
from app.modules.alerting.domain.models import Department
from app.modules.generation.domain.models import ClusterContext

_PERSONA = (
    "Bạn là chuyên gia cảnh báo khủng hoảng truyền thông của ZaloPay (ZLP) — ví điện "
    "tử thuộc VNG. CHỈ về ZaloPay, KHÔNG bao gồm Zalo (app chat). Viết brief tiếng "
    "Việt, Markdown sạch (heading/bullet/in đậm), ngắn gọn, hướng hành động."
)


@dataclass(frozen=True)
class ComposeBriefUseCase:
    llm: Any
    prompt: str
    model_name: str

    async def execute(self, ctx: ClusterContext, department: Department) -> str:
        user = (
            f"{self.prompt}\n\n## Phòng ban tiếp nhận\n{department.name}"
            f"\n\n## Ngữ cảnh vấn đề của cụm\n{ctx.to_prompt_block()}"
        )
        # Brief alert ưu tiên tốc độ → trần token vừa phải.
        return await complete_text(
            self.llm,
            [Message("system", [_PERSONA]), Message("user", [user])],
            max_tokens=1200,
        )
