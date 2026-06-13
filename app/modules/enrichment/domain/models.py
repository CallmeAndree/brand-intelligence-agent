from typing import Literal

from pydantic import BaseModel, Field


BiIntent = Literal[
    "khiếu nại/phàn nàn",
    "hỏi/cần hỗ trợ",
    "cảnh báo/tố cáo",
    "mỉa mai/châm biếm",
    "so sánh đối thủ",
    "góp ý/đề xuất",
    "spam/cảm thán/vô nghĩa",
]

BiProductArea = Literal[
    "thanh toán & hóa đơn",
    "chuyển/nạp/rút tiền",
    "liên kết ngân hàng/thẻ",
    "chứng khoán",
    "ví & số dư",
    "tài khoản & bảo mật",
    "khuyến mãi & hoàn tiền",
    "hiệu năng & lỗi app",
    "CSKH & hỗ trợ",
    "khác",
]

BI_INTENT_VALUES = list(BiIntent.__args__)
BI_PRODUCT_AREA_VALUES = list(BiProductArea.__args__)


class TopicFields(BaseModel):
    bi_topic: str = Field(min_length=1, description="Chủ đề/vấn đề cốt lõi dư luận đang phản ánh, từ vựng mở, cụm ngắn tiếng Việt.")
    bi_product_area: BiProductArea = Field(
        description=(
            "Mảng sản phẩm/tính năng CỤ THỂ bên trong ZaloPay bị nhắc tới. KHÔNG ghi 'ZaloPay' chung chung."
        ),
    )
    bi_keywords: list[str] = Field(
        default_factory=list,
        description=(
            "3–7 từ khóa/cụm từ tiếng Việt ngắn gọn rút ra từ mention, dùng để gom nhóm xu hướng & tìm kiếm "
            "(ví dụ: 'trừ tiền sai', 'không hoàn tiền', 'app văng'). Mỗi từ khóa viết thường, không trùng lặp, "
            "KHÔNG chứa từ 'ZaloPay'."
        ),
    )


class JudgmentFields(BaseModel):
    bi_severity: int = Field(ge=1, le=10, description="Mức rủi ro truyền thông 1–10 (10 = khủng hoảng khẩn: lừa đảo/mất tiền diện rộng, pháp lý/bảo mật, viral bôi nhọ thương hiệu).")
    bi_intent: BiIntent = Field(description="Ý định thật sự của người nói, chọn đúng một giá trị trong tập enum đóng.")
    bi_is_actionable: bool = Field(description="true nếu đây là vấn đề CẦN can thiệp/xử lý SỚM — có nguy cơ thành khủng hoảng truyền thông nếu để lâu; false nếu chỉ là than phiền lẻ tẻ, cảm thán, rác, không cần phản ứng gấp.")


class SummaryField(BaseModel):
    bi_summary_vi: str = Field(min_length=1, description="Một câu tiếng Việt NGẮN GỌN cho bản tin theo dõi truyền thông thương hiệu ZaloPay.")


class BiFields(TopicFields, JudgmentFields, SummaryField):
    pass
