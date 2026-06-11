from pydantic import BaseModel, Field


class TopicFields(BaseModel):
    bi_topic: str = Field(min_length=1, description="Chủ đề/vấn đề cốt lõi dư luận đang phản ánh, từ vựng mở, cụm ngắn tiếng Việt.")
    bi_product_area: str = Field(
        min_length=1,
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
    bi_intent: str = Field(min_length=1, description="Ý định thật sự của người nói, mô tả ngắn tiếng Việt.")
    bi_is_actionable: bool = Field(description="true nếu đây là vấn đề CẦN can thiệp/xử lý SỚM — có nguy cơ thành khủng hoảng truyền thông nếu để lâu; false nếu chỉ là than phiền lẻ tẻ, cảm thán, rác, không cần phản ứng gấp.")


class SummaryField(BaseModel):
    bi_summary_vi: str = Field(min_length=1, description="Một câu tiếng Việt cho bản tin theo dõi truyền thông thương hiệu ZaloPay.")


class BiFields(TopicFields, JudgmentFields, SummaryField):
    pass
