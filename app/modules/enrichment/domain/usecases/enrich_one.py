import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

from agent_framework import ChatOptions, Message
from pydantic import BaseModel, ValidationError

from app.modules.enrichment.domain.models import BiFields, JudgmentFields, SummaryField, TopicFields
from app.modules.ingestion.domain.models import Mention

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True)
class EnrichOneUseCase:
    llm: Any

    # Persona dùng chung cho cả 3 pass: agent này CHỈ theo dõi ZaloPay nên không
    # bao giờ ghi lại "ZaloPay" như một nhãn vô nghĩa — luôn nói về sắc thái
    # truyền thông và phân vùng sản phẩm cụ thể.
    _BRAND_PERSONA = (
        "Bạn là chuyên gia phân tích thương hiệu & truyền thông của ZaloPay — ví điện tử "
        "thuộc VNG. Mọi mention đưa vào đều là phản hồi tiêu cực về ZaloPay trên mạng xã hội."
        "Bạn đọc dư luận như một người làm truyền thông thương hiệu: nhận diện đúng mảng "
        "sản phẩm bị nhắc, sắc thái cảm xúc, và mức rủi ro đối với uy tín thương hiệu."
    )

    async def execute(self, mention: Mention) -> BiFields:
        topic = await self._call(
            [
                Message("system", [self._BRAND_PERSONA + " Nhiệm vụ pass này: phân loại chủ đề và xác định mảng sản phẩm/ nội dung cụ thể được nhắc đến tr. Chỉ trả về đúng object JSON được yêu cầu, không trả schema."]),
                Message("user", [self._topic_prompt(mention)]),
            ],
            TopicFields,
            lambda: self._fallback_topic(mention),
        )
        judgment = await self._call(
            [
                Message("system", [self._BRAND_PERSONA + " Nhiệm vụ pass này: đánh giá mức độ nghiêm trọng dưới góc nhìn rủi ro truyền thông thương hiệu, đọc ý định người nói và khả năng đội ngũ xử lý. Chỉ trả về đúng object JSON được yêu cầu, không trả schema."]),
                Message("user", [self._judgment_prompt(mention, topic)]),
            ],
            JudgmentFields,
            lambda: self._fallback_judgment(mention),
        )
        summary = await self._call(
            [
                Message("system", [self._BRAND_PERSONA + " Nhiệm vụ pass này: viết một câu tóm tắt tiếng Việt sắc bén, đúng giọng một bản tin theo dõi truyền thông thương hiệu. Chỉ trả về đúng object JSON được yêu cầu, không trả schema."]),
                Message("user", [self._summary_prompt(mention, topic)]),
            ],
            SummaryField,
            lambda: self._fallback_summary(mention, topic),
        )
        return BiFields(**topic.model_dump(), **judgment.model_dump(), **summary.model_dump())

    async def _call(self, messages: list[Message], schema: type[SchemaT], fallback_factory: Any | None = None) -> SchemaT:
        schema_prompt = self._schema_prompt(schema)
        try:
            response = await self.llm.get_response(messages, options=ChatOptions(response_format=schema))
            value = getattr(response, "value", None)
            if isinstance(value, schema):
                return value
            if value is not None:
                return self._validate_value(value, schema)
        except Exception:
            pass

        fallback_messages = messages + [Message("user", [schema_prompt])]
        try:
            response = await self.llm.get_response(fallback_messages)
            return self._validate_value(self._extract_json(self._response_text(response)), schema)
        except Exception:
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
                if fallback_factory is not None:
                    return fallback_factory()
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
    def _fallback_topic(mention: Mention) -> TopicFields:
        text = mention.mention.lower()
        if any(keyword in text for keyword in ("ví trả sau", "vi tra sau", "vitrả sau")):
            return TopicFields(bi_topic="thắc mắc phí hủy ví trả sau", bi_product_area="ví trả sau")
        if any(keyword in text for keyword in ("mbbank", "ngân hàng", "nap", "nạp", "rút", "rut")):
            return TopicFields(bi_topic="lỗi nạp rút hoặc liên kết ngân hàng", bi_product_area="nạp–rút tiền/liên kết ngân hàng")
        if any(keyword in text for keyword in ("clone", "lừa", "lua", "scam")):
            return TopicFields(bi_topic="nghi ngờ lừa đảo hoặc tài khoản ảo", bi_product_area="bảo mật/lừa đảo")
        return TopicFields(bi_topic="phản hồi tiêu cực chung", bi_product_area="tổng quát")

    @staticmethod
    def _fallback_judgment(mention: Mention) -> JudgmentFields:
        text = mention.mention.lower()
        high_risk = any(keyword in text for keyword in ("lừa", "lua", "scam", "mất tiền", "mat tien", "hack"))
        question = "?" in text or any(keyword in text for keyword in ("không", "khong", "có", "co", "ạ", "a"))
        return JudgmentFields(
            bi_severity=7 if high_risk else 3,
            bi_intent="cảnh báo/nghi ngờ rủi ro" if high_risk else ("hỏi thông tin" if question else "than phiền lẻ tẻ"),
            bi_is_actionable=high_risk,
        )

    @staticmethod
    def _fallback_summary(mention: Mention, topic: TopicFields) -> SummaryField:
        return SummaryField(
            bi_summary_vi=f"Dư luận phản ánh {topic.bi_topic} liên quan đến {topic.bi_product_area}, cần theo dõi để đánh giá tác động tới cảm nhận thương hiệu."
        )

    @staticmethod
    def _topic_prompt(mention: Mention) -> str:
        return f"""
Bóc tách hai trường phân loại cho mention tiêu cực về ZaloPay dưới đây.
- bi_topic: chủ đề/vấn đề cốt lõi mà dư luận đang nói, từ vựng mở, một cụm ngắn gọn tiếng Việt (ví dụ "nghi ngờ lừa đảo", "trừ tiền sai", "app lỗi không vào được", "khuyến mãi gây hiểu lầm").
- bi_product_area: MẢNG SẢN PHẨM/TÍNH NĂNG CỤ THỂ bên trong ZaloPay bị nhắc tới. TUYỆT ĐỐI KHÔNG ghi "ZaloPay" chung chung (vô nghĩa vì mọi mention đều về ZaloPay). Hãy chọn mảng cụ thể, ví dụ: thanh toán/chuyển tiền, nạp–rút tiền, liên kết ngân hàng, mã QR, ví trả sau, khuyến mãi/voucher, định danh (KYC)/đăng nhập, chăm sóc khách hàng, bảo mật/lừa đảo, hiệu năng ứng dụng. Nếu không xác định được mảng cụ thể thì mới ghi "tổng quát".

Mention: {mention.mention}
Author: {mention.author or ''}
Subject: {mention.subject or ''}
Kompa analysis: {mention.kompa_analysis or ''}
""".strip()

    @staticmethod
    def _judgment_prompt(mention: Mention, topic: TopicFields) -> str:
        return f"""
Đã xác định chủ đề bi_topic={topic.bi_topic!r}. Hãy đánh giá mention này dưới góc nhìn một người làm truyền thông thương hiệu ZaloPay.
- bi_severity (mức rủi ro truyền thông, 1–10): 1–2 = than phiền lẻ tẻ, vô hại; 3–4 = bất mãn nhẹ; 5–6 = khiếu nại rõ ràng cần ghi nhận; 7–8 = sự cố dịch vụ ảnh hưởng nhiều người hoặc dễ lan; 9–10 = khủng hoảng khẩn (lừa đảo/mất tiền diện rộng, vấn đề pháp lý/bảo mật, nội dung đang viral bôi nhọ thương hiệu).
- bi_intent: ý định thật sự của người nói, mô tả ngắn bằng tiếng Việt (ví dụ "khiếu nại đòi hoàn tiền", "cảnh báo người khác", "mỉa mai châm biếm", "hỏi thông tin", "spam/lạc đề").
- bi_is_actionable: true nếu đây là vấn đề CẦN can thiệp/xử lý SỚM (có nguy cơ leo thang thành khủng hoảng truyền thông nếu để lâu); false nếu chỉ là than phiền lẻ tẻ, cảm thán, rác, hoặc không cần phản ứng gấp.

Mention: {mention.mention}
Mảng sản phẩm: {topic.bi_product_area}
""".strip()

    @staticmethod
    def _summary_prompt(mention: Mention, topic: TopicFields) -> str:
        return f"""
Viết MỘT câu tiếng Việt súc tích cho bản tin theo dõi truyền thông thương hiệu ZaloPay, đúng giọng một nhà phân tích truyền thông: nêu rõ dư luận đang phản ánh điều gì và vì sao nó đáng chú ý với thương hiệu. Không lặp lại nguyên văn mention, không mở đầu bằng "Người dùng nói rằng".
Chủ đề: {topic.bi_topic}
Mention: {mention.mention}
""".strip()
