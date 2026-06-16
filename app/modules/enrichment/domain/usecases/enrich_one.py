import json
import re
import typing
from dataclasses import dataclass
from typing import Any, TypeVar

from agent_framework import ChatOptions, Message
from pydantic import BaseModel, ValidationError

from app.core.errors import is_rate_limit_error
from app.modules.enrichment.domain.models import (
    BI_INTENT_VALUES,
    BI_PRODUCT_AREA_GUIDE,
    BI_PRODUCT_AREA_VALUES,
    BI_SEVERITY_FACTOR_VALUES,
    BiFields,
    JudgmentFields,
    SummaryField,
    TopicFields,
)
from app.modules.ingestion.domain.models import Mention

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Lớp escalation TẤT ĐỊNH: ép SÀN bi_severity theo tiêu chí rủi ro (factors) + ý định,
# để mention lừa đảo/pháp lý/bảo mật KHÔNG bao giờ bị LLM chấm hụt. Sàn cao nhất thắng.
_FACTOR_FLOOR: dict[str, int] = {
    "mất tiền": 8,
    "lừa đảo/giả mạo": 8,
    "pháp lý": 8,
    "bảo mật/lộ dữ liệu": 8,
    "ảnh hưởng diện rộng": 7,
    "lan truyền/viral": 7,
    "bôi nhọ thương hiệu": 7,
}
_INTENT_FLOOR: dict[str, int] = {"cảnh báo/tố cáo": 7}
_INTENT_CEILING: dict[str, int] = {"spam/cảm thán/vô nghĩa": 3}  # rác → trần thấp


def normalize_severity_factors(factors: list[str] | None) -> list[str]:
    """Giữ lại các factor hợp lệ (tập đóng), bỏ trùng — phòng LLM trả nhãn lạ."""
    seen: list[str] = []
    for f in factors or []:
        if f in BI_SEVERITY_FACTOR_VALUES and f not in seen:
            seen.append(f)
    return seen


def apply_severity_floor(score: int, factors: list[str], intent: str | None) -> int:
    """Clamp bi_severity theo factors + intent. THUẦN (test được).

    Sàn: factor rủi ro cao (mất tiền/lừa đảo/pháp lý/bảo mật)→8; lan toả→7; intent
    'cảnh báo/tố cáo'→7. Trần: intent 'spam/...'→3 (rác, áp sau cùng). Kết quả ∈ [1,10].
    """
    floor = 0
    for f in factors:
        floor = max(floor, _FACTOR_FLOOR.get(f, 0))
    floor = max(floor, _INTENT_FLOOR.get(intent or "", 0))
    score = max(score, floor)
    ceiling = _INTENT_CEILING.get(intent or "")
    if ceiling is not None:
        score = min(score, ceiling)
    return max(1, min(10, score))


@dataclass(frozen=True)
class EnrichOneUseCase:
    llm: Any

    # Persona dùng chung cho cả 3 pass: agent này CHỈ theo dõi Zalopay nên không
    # bao giờ ghi lại "Zalopay" như một nhãn vô nghĩa — luôn nói về sắc thái
    # truyền thông và phân vùng sản phẩm cụ thể.
    _BRAND_PERSONA = (
        "Bạn là chuyên gia phân tích thương hiệu & truyền thông của Zalopay (ZLP) — ví điện tử "
        "thuộc tập đoàn VNG. CHỈ về Zalopay, KHÔNG bao gồm Zalo (app chat là sản phẩm khác của VNG). "
        "Mọi mention đưa vào đều là phản hồi tiêu cực về Zalopay trên mạng xã hội."
        "Khi viết tên thương hiệu PHẢI đúng là 'Zalopay' (Z hoa, còn lại thường liền nhau), "
        "KHÔNG viết 'ZaloPay'/'Zalo Pay'/'zalopay'."
        "Bạn đọc dư luận như một người làm truyền thông thương hiệu: nhận diện đúng mảng "
        "sản phẩm bị nhắc, sắc thái cảm xúc, và mức rủi ro đối với uy tín thương hiệu."
    )

    async def execute(self, mention: Mention) -> BiFields:
        # Chain đầy đủ 3 pass — dùng cho backfill/replay/test. Worker on-ingest gọi
        # từng pass riêng (topic/judgment/summary) để persist tăng dần + resume.
        topic = await self.topic(mention)
        judgment = await self.judgment(mention, topic)
        summary = await self.summary(mention, topic)
        return BiFields(**topic.model_dump(), **judgment.model_dump(), **summary.model_dump())

    async def topic(self, mention: Mention) -> TopicFields:
        return await self._call(
            [
                Message("system", [self._BRAND_PERSONA + " Nhiệm vụ pass này: phân loại chủ đề và xác định mảng sản phẩm/ nội dung cụ thể được nhắc đến tr. Chỉ trả về đúng object JSON được yêu cầu, không trả schema."]),
                Message("user", [self._topic_prompt(mention)]),
            ],
            TopicFields,
        )

    async def judgment(self, mention: Mention, topic: TopicFields) -> JudgmentFields:
        j = await self._call(
            [
                Message("system", [self._BRAND_PERSONA + " Nhiệm vụ pass này: đánh giá mức độ nghiêm trọng dưới góc nhìn rủi ro truyền thông thương hiệu, đọc ý định người nói và khả năng đội ngũ xử lý. Chỉ trả về đúng object JSON được yêu cầu, không trả schema."]),
                Message("user", [self._judgment_prompt(mention, topic)]),
            ],
            JudgmentFields,
        )
        # Escalation tất định: chuẩn hoá factors + ép sàn/trần bi_severity theo tiêu chí
        # rủi ro & ý định (LLM holistic ở giữa thang, lề rủi ro do luật chốt).
        factors = normalize_severity_factors(j.bi_severity_factors)
        new_severity = apply_severity_floor(j.bi_severity, factors, j.bi_intent)
        return j.model_copy(update={"bi_severity": new_severity, "bi_severity_factors": factors})

    async def summary(self, mention: Mention, topic: TopicFields) -> SummaryField:
        return await self._call(
            [
                Message("system", [self._BRAND_PERSONA + " Nhiệm vụ pass này: viết một câu tóm tắt tiếng Việt sắc bén, đúng giọng một bản tin theo dõi truyền thông thương hiệu. Chỉ trả về đúng object JSON được yêu cầu, không trả schema."]),
                Message("user", [self._summary_prompt(mention, topic)]),
            ],
            SummaryField,
        )

    async def _call(self, messages: list[Message], schema: type[SchemaT]) -> SchemaT:
        schema_prompt = self._schema_prompt(schema)
        try:
            response = await self.llm.get_response(messages, options=ChatOptions(response_format=schema))
            value = getattr(response, "value", None)
            if isinstance(value, schema):
                return value
            if value is not None:
                return self._validate_value(value, schema)
        except Exception as exc:
            # 429 là rate-limit (transient), KHÔNG phải lỗi schema → raise ngay để
            # worker giữ pending + thử lại sau, tránh đốt thêm call fallback dồn dập.
            if is_rate_limit_error(exc):
                raise

        fallback_messages = messages + [Message("user", [schema_prompt])]
        try:
            response = await self.llm.get_response(fallback_messages)
            return self._validate_value(self._extract_json(self._response_text(response)), schema)
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise
            repair_messages = fallback_messages + [
                Message(
                    "user",
                    [
                        "Your previous response was invalid because it returned a JSON schema or missed required fields. "
                        f"Return ONLY this JSON object shape with real values: {self._example_object(schema)}"
                    ],
                )
            ]
            response = await self.llm.get_response(repair_messages)
            try:
                return self._validate_value(self._extract_json(self._response_text(response)), schema)
            except (ValueError, ValidationError):
                raise

    @staticmethod
    def _schema_prompt(schema: type[BaseModel]) -> str:
        properties = schema.model_json_schema().get("properties", {})
        required_fields = ", ".join(properties.keys())
        return (
            "Reply with a single valid JSON object only, no markdown, no JSON schema, no properties/type/title keys. "
            f"The object must include exactly these fields with real analyzed values: {required_fields}. "
            f"Example shape: {EnrichOneUseCase._example_object(schema)}"
        )

    @staticmethod
    def _example_object(schema: type[BaseModel]) -> str:
        examples: dict[str, Any] = {}
        for field_name, field_info in schema.model_fields.items():
            annotation = field_info.annotation
            if annotation is bool:
                examples[field_name] = False
            elif annotation is int:
                examples[field_name] = 3
            elif typing.get_origin(annotation) in (list, set, tuple):
                examples[field_name] = ["từ khóa 1", "từ khóa 2", "từ khóa 3"]
            elif field_name == "bi_product_area":
                examples[field_name] = BI_PRODUCT_AREA_VALUES[0]
            elif field_name == "bi_intent":
                examples[field_name] = BI_INTENT_VALUES[0]
            else:
                examples[field_name] = "giá trị phân tích"
        return json.dumps(examples, ensure_ascii=False)

    @staticmethod
    def _validate_value(value: Any, schema: type[SchemaT]) -> SchemaT:
        if isinstance(value, str):
            return schema.model_validate_json(value)
        if isinstance(value, dict) and "properties" in value and not any(field in value for field in schema.model_fields):
            raise ValueError("LLM returned a JSON schema instead of field values")
        return schema.model_validate(value)

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if text:
            return str(text)
        value = getattr(response, "value", None)
        if value is not None:
            return str(value)
        return str(response)

    @staticmethod
    def _extract_json(text: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in LLM response")
        return text[start : end + 1]

    @staticmethod
    def _topic_prompt(mention: Mention) -> str:
        product_areas = ", ".join(f'"{value}"' for value in BI_PRODUCT_AREA_VALUES)
        area_guide = "\n".join(
            f"          • {name}: {desc}" for name, desc in BI_PRODUCT_AREA_GUIDE.items()
        )
        return f"""
        Bóc tách ba trường phân loại cho mention tiêu cực về Zalopay dưới đây.
        - bi_topic: chủ đề/vấn đề cốt lõi mà dư luận đang nói, từ vựng mở, một cụm ngắn gọn tiếng Việt (ví dụ "nghi ngờ lừa đảo", "trừ tiền sai", "app lỗi không vào được", "khuyến mãi gây hiểu lầm").
        - bi_product_area: CHỌN ĐÚNG 1 giá trị trong tập enum đóng sau: {product_areas}. Đây là MẢNG NGHIỆP VỤ của Zalopay mà mention nói tới — bám đúng định nghĩa từng mảng:
{area_guide}
          Quy tắc: BẮT BUỘC chọn ĐÚNG 1 trong các mảng trên — KHÔNG có lựa chọn "Others"/"khác". Chọn mảng nghiệp vụ CỤ THỂ nếu nội dung nhắc rõ dịch vụ đó. Nếu là vấn đề XUYÊN SUỐT không gắn riêng một dịch vụ (lỗi app/đăng nhập, bảo mật/khóa tài khoản, CSKH/tổng đài, giao diện chung, ví & số dư), hãy gắn vào mảng dịch vụ mà người dùng ĐANG thao tác hoặc BỊ ẢNH HƯỞNG theo ngữ cảnh (vd: không đăng nhập để chuyển tiền → Transfer; khóa tài khoản/liên kết ngân hàng → Binding; lỗi nạp tiền điện thoại → Telco; CSKH về khuyến mãi → Loyalty). Nếu thực sự không có manh mối, chọn mảng CỐT LÕI khả dĩ nhất (ưu tiên Transfer vì là ví core). TUYỆT ĐỐI KHÔNG ghi "Zalopay" chung chung.
        - bi_keywords: 3–7 từ khóa/cụm từ tiếng Việt NGẮN GỌN rút trực tiếp từ nội dung mention, phục vụ gom nhóm xu hướng & tìm kiếm. Mỗi từ khóa PHẢI mang nội dung cụ thể (vấn đề/đối tượng), ví dụ ["trừ tiền sai", "không hoàn tiền", "tổng đài không phản hồi", "liên kết ngân hàng lỗi"]. TUYỆT ĐỐI KHÔNG trả từ khóa rỗng nghĩa chỉ gồm phủ định/cảm thán ("không được", "chưa thấy", "không dùng", "nói không", "ảo quá"). Viết thường, mỗi từ khóa là một cụm súc tích không trùng lặp, KHÔNG đưa từ "Zalopay" vào.

        Mention: {mention.mention}
        Author: {mention.author or ''}
        Subject: {mention.subject or ''}
        Kompa analysis: {mention.kompa_analysis or ''}
        """.strip()

    @staticmethod
    def _judgment_prompt(mention: Mention, topic: TopicFields) -> str:
        intents = ", ".join(f'"{value}"' for value in BI_INTENT_VALUES)
        factors = ", ".join(f'"{value}"' for value in BI_SEVERITY_FACTOR_VALUES)
        return f"""
        Đã xác định chủ đề bi_topic={topic.bi_topic!r}. Hãy đánh giá mention này dưới góc nhìn một người làm truyền thông thương hiệu Zalopay.
        - bi_severity (mức rủi ro truyền thông, 1–10): 1–2 = than phiền lẻ tẻ, vô hại; 3–4 = bất mãn nhẹ; 5–6 = khiếu nại rõ ràng cần ghi nhận; 7–8 = sự cố dịch vụ ảnh hưởng nhiều người hoặc dễ lan; 9–10 = khủng hoảng khẩn (lừa đảo/mất tiền diện rộng, vấn đề pháp lý/bảo mật, nội dung đang viral bôi nhọ thương hiệu).
        - bi_severity_factors: LIỆT KÊ các tiêu chí rủi ro NỔI BẬT trong mention, chọn 0..n giá trị TRONG TẬP ĐÓNG sau (đúng nguyên văn, để trống [] nếu không có): {factors}. Gắn 'mất tiền' khi người dùng bị/đang lo mất tiền; 'lừa đảo/giả mạo' khi có dấu hiệu scam/mạo danh; 'pháp lý' khi doạ kiện/báo chí/cơ quan chức năng; 'bảo mật/lộ dữ liệu' khi lộ thông tin/tài khoản; 'ảnh hưởng diện rộng' khi nhiều người gặp; 'lan truyền/viral' khi đang được chia sẻ mạnh; 'bôi nhọ thương hiệu' khi nội dung công kích/hạ uy tín.
        - bi_intent: CHỌN ĐÚNG 1 giá trị trong tập enum đóng sau: {intents}.
        - bi_is_actionable: true nếu đây là vấn đề CẦN can thiệp/xử lý SỚM (có nguy cơ leo thang thành khủng hoảng truyền thông nếu để lâu); false nếu chỉ là than phiền lẻ tẻ, cảm thán, rác, hoặc không cần phản ứng gấp.

        Mention: {mention.mention}
        Mảng sản phẩm: {topic.bi_product_area}
        """.strip()

    @staticmethod
    def _summary_prompt(mention: Mention, topic: TopicFields) -> str:
        return f"""
        Viết MỘT câu tiếng Việt súc tích cho bản tin theo dõi truyền thông thương hiệu Zalopay, đúng giọng một nhà phân tích truyền thông: nêu rõ dư luận đang phản ánh điều gì và vì sao nó đáng chú ý với thương hiệu. Không lặp lại nguyên văn mention, không mở đầu bằng "Người dùng nói rằng".
        Chủ đề: {topic.bi_topic}
        Mention: {mention.mention}
        """.strip()
