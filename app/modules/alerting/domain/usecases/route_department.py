"""RouteDepartmentUseCase — map cụm → phòng ban theo rule playbook `.md`.

Rule dạng dòng `product_area_substring => Tên phòng ban` (đọc từ
`alert/department_routing.md`). Khớp theo `bi_product_area` (ưu tiên) rồi nhãn cụm/
sample_topics. Không khớp → fallback Marketing/PR. Thuần (không I/O) để test dễ.
"""

from dataclasses import dataclass

from app.modules.alerting.domain.models import Department
from app.modules.generation.domain.models import ClusterContext

_FALLBACK = "Marketing/PR"


@dataclass(frozen=True)
class RouteDepartmentUseCase:
    rules: str  # nội dung playbook department_routing.md

    def _parse_rules(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for line in self.rules.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=>" not in line:
                continue
            key, _, dept = line.partition("=>")
            key, dept = key.strip().lower(), dept.strip()
            if key and dept:
                pairs.append((key, dept))
        return pairs

    def execute(self, ctx: ClusterContext) -> Department:
        rules = self._parse_rules()
        # Gom văn bản đại diện cụm để dò khớp.
        haystacks = [ctx.label.lower()]
        haystacks += [t.lower() for t in ctx.sample_topics]
        haystacks += [
            (m.product_area or "").lower() for m in ctx.top_mentions if m.product_area
        ]
        blob = " | ".join(haystacks)

        for key, dept in rules:
            if key in blob:
                return Department(name=dept, rationale=f"khớp rule '{key}'")
        return Department(name=_FALLBACK, rationale="không khớp rule — fallback")
