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

# Tiêu chí RỦI RO kích hoạt (LLM tự gắn ở pass judgment) — vừa giải thích "vì sao điểm
# này", vừa là input cho lớp escalation tất định ép sàn bi_severity (xem apply_severity_floor).
BiSeverityFactor = Literal[
    "mất tiền",
    "lừa đảo/giả mạo",
    "pháp lý",
    "bảo mật/lộ dữ liệu",
    "ảnh hưởng diện rộng",
    "lan truyền/viral",
    "bôi nhọ thương hiệu",
]

# Mảng nghiệp vụ Zalopay (theo các use-case sản phẩm thực tế) — đây cũng là KHÓA
# điều phối alert về phòng ban (Telco→TELCO, Loyalty→LOYALTY, Transfer→TRANSFER,
# còn lại→hộp chung). Nhãn canonical tiếng Anh để đồng bộ tên phòng ban + routing.
BiProductArea = Literal[
    "Transfer",
    "Bill",
    "OTA",
    "Telco",
    "Binding",
    "Financial Service",
    "Loyalty",
    "Daily Life Service",
    "Entertainment",
]

BI_INTENT_VALUES = list(BiIntent.__args__)
BI_PRODUCT_AREA_VALUES = list(BiProductArea.__args__)
BI_SEVERITY_FACTOR_VALUES = list(BiSeverityFactor.__args__)

# Định nghĩa từng mảng (tiếng Việt + ví dụ) để LLM phân loại CHÍNH XÁC. Dùng render
# vào prompt enrich. Giữ ở domain dạng dữ liệu thuần (không I/O).
BI_PRODUCT_AREA_GUIDE: dict[str, str] = {
    "Transfer": (
        "Chuyển tiền / nhận tiền giữa người dùng, nạp ví, rút tiền về ngân hàng, "
        "chuyển khoản liên ngân hàng, lì xì/chuyển tiền qua QR cá nhân, giao dịch chuyển tiền."
    ),
    "Bill": (
        "Thanh toán hóa đơn dịch vụ định kỳ: điện, nước, internet, truyền hình cáp, "
        "phí chung cư/quản lý, hóa đơn điện thoại trả sau, học phí định kỳ qua hóa đơn."
    ),
    "OTA": (
        "Đặt & thanh toán du lịch trực tuyến: vé máy bay, khách sạn, tour, vé tàu/xe khách, "
        "phòng nghỉ (Online Travel Agency)."
    ),
    "Telco": (
        "Dịch vụ viễn thông: nạp tiền điện thoại (top-up), mua data 3G/4G/5G, thẻ cào, "
        "gói cước di động, nạp điện thoại trả trước."
    ),
    "Binding": (
        "Liên kết / hủy liên kết nguồn tiền: liên kết ngân hàng, thẻ ATM nội địa, thẻ "
        "Visa/Mastercard/JCB, liên kết ví Cake, xác thực OTP khi liên kết, gỡ liên kết."
    ),
    "Financial Service": (
        "Dịch vụ tài chính: đầu tư, chứng khoán, vay tiêu dùng/trả góp, bảo hiểm, tích lũy "
        "sinh lời, số dư sinh lời, tra cứu CIC/điểm tín dụng."
    ),
    "Loyalty": (
        "Khuyến mãi & khách hàng thân thiết: ưu đãi/voucher, hoàn tiền (cashback), tích điểm, "
        "hạng/thăng hạng thành viên, quà tặng, mini-game thưởng, quay số trúng thưởng, lì xì khuyến mãi."
    ),
    "Daily Life Service": (
        "Thanh toán đời sống hằng ngày: quét QR tại cửa hàng/siêu thị, ăn uống, mua sắm, "
        "đi lại (taxi/xe công nghệ), dịch vụ công, ủng hộ/từ thiện, mua mã thẻ dịch vụ khác."
    ),
    "Entertainment": (
        "Giải trí: nạp game, mini-game giải trí, mua vé xem phim, nhạc, nội dung số giải trí."
    ),
}


class TopicFields(BaseModel):
    bi_topic: str = Field(min_length=1, description="Chủ đề/vấn đề cốt lõi dư luận đang phản ánh, từ vựng mở, cụm ngắn tiếng Việt.")
    bi_product_area: BiProductArea = Field(
        description=(
            "Mảng sản phẩm/tính năng CỤ THỂ bên trong Zalopay bị nhắc tới. KHÔNG ghi 'Zalopay' chung chung."
        ),
    )
    bi_keywords: list[str] = Field(
        default_factory=list,
        description=(
            "3–7 từ khóa/cụm từ tiếng Việt ngắn gọn rút ra từ mention, dùng để gom nhóm xu hướng & tìm kiếm "
            "(ví dụ: 'trừ tiền sai', 'không hoàn tiền', 'app văng'). Mỗi từ khóa viết thường, không trùng lặp, "
            "KHÔNG chứa từ 'Zalopay'."
        ),
    )


class JudgmentFields(BaseModel):
    bi_severity: int = Field(ge=1, le=10, description="Mức rủi ro truyền thông 1–10 (10 = khủng hoảng khẩn: lừa đảo/mất tiền diện rộng, pháp lý/bảo mật, viral bôi nhọ thương hiệu).")
    bi_severity_factors: list[BiSeverityFactor] = Field(
        default_factory=list,
        description=(
            "Các tiêu chí rủi ro NỔI BẬT trong mention (0..n, chọn từ tập đóng): "
            "'mất tiền', 'lừa đảo/giả mạo', 'pháp lý', 'bảo mật/lộ dữ liệu', "
            "'ảnh hưởng diện rộng', 'lan truyền/viral', 'bôi nhọ thương hiệu'. "
            "Để trống nếu không có. Đây là căn cứ giải thích cho điểm severity."
        ),
    )
    bi_intent: BiIntent = Field(description="Ý định thật sự của người nói, chọn đúng một giá trị trong tập enum đóng.")
    bi_is_actionable: bool = Field(description="true nếu đây là vấn đề CẦN can thiệp/xử lý SỚM — có nguy cơ thành khủng hoảng truyền thông nếu để lâu; false nếu chỉ là than phiền lẻ tẻ, cảm thán, rác, không cần phản ứng gấp.")


class SummaryField(BaseModel):
    bi_summary_vi: str = Field(min_length=1, description="Một câu tiếng Việt NGẮN GỌN cho bản tin theo dõi truyền thông thương hiệu Zalopay.")


class BiFields(TopicFields, JudgmentFields, SummaryField):
    pass
