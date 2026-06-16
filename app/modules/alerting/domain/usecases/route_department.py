"""RouteDepartmentUseCase — điều phối một cụm về ĐÚNG phòng ban + email.

Tín hiệu điều phối CHÍNH là `bi_product_area` (taxonomy 10 mảng nghiệp vụ Zalopay,
nhãn canonical tiếng Anh). Chọn mảng PHỔ BIẾN NHẤT trong các mention của cụm rồi map
về ĐÚNG 1 trong 3 phòng (TELCO/LOYALTY/TRANSFER) — KHÔNG còn phòng fallback Brand/PR;
cả 10 mảng đều có phòng (map ngữ nghĩa ở main.py). Mảng không xác định → `fallback`
(đặt = TRANSFER ở main.py). Thuần (không I/O) để test dễ.

`routes`/`fallback` được build từ settings ở main.py (email lấy từ .env), nên use
case không phụ thuộc env trực tiếp.
"""

from dataclasses import dataclass

from app.modules.alerting.domain.models import Department
from app.modules.generation.domain.models import ClusterContext


@dataclass(frozen=True)
class RouteDepartmentUseCase:
    routes: dict[str, Department]  # product_area canonical -> Department(name,email)
    fallback: Department

    def _dominant_product_area(self, ctx: ClusterContext) -> str | None:
        counts: dict[str, int] = {}
        for m in ctx.top_mentions:
            area = (m.product_area or "").strip()
            if area:
                counts[area] = counts.get(area, 0) + 1
        if not counts:
            return None
        # Mảng có nhiều mention nhất (tie-break theo tên cho ổn định/deterministic).
        return max(sorted(counts), key=lambda area: counts[area])

    def execute(self, ctx: ClusterContext) -> Department:
        area = self._dominant_product_area(ctx)
        if area and area in self.routes:
            dept = self.routes[area]
            return dept.model_copy(
                update={"rationale": f"mảng '{area}' → phòng {dept.name}"}
            )
        return self.fallback.model_copy(
            update={"rationale": f"mảng '{area or 'không xác định'}' → phòng {self.fallback.name} (mặc định)"}
        )
