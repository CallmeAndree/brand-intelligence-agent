"""Sinh text thuần (KHÔNG structured/JSON) dùng chung cho monitor + alert.

Lý do tách: ép `response_format=schema` lên MINIMAX khiến output bị cụt (model
trả JSON tối giản, thường chỉ 1 dòng tiêu đề) + kích hoạt fallback 3 mức (nhân
2–3 round-trip → chậm). Với artifact/brief vốn chỉ là **một khối Markdown**,
sinh text thẳng vừa đầy đủ hơn vừa nhanh hơn và **stream được từng token**.

MINIMAX (`minimax-m2.5`) là **reasoning model** → nhả block `<think>…</think>` ở
đầu output (cả khi stream lẫn non-stream). Phải LỌC BỎ trước khi hiển thị/lưu, nếu
không artifact sẽ lẫn chuỗi suy luận. `stream_text` lọc theo state-machine để chỉ
emit phần trả lời (sau `</think>`); `complete_text` strip bằng regex.

- `complete_text`: 1 call, trả full text đã sạch think (fallback non-stream).
- `stream_text`: async-iter từng delta text đã bỏ think (SSE).
429 (rate-limit) cứ raise lên cho caller xử lý như cũ.
"""

import re
from typing import Any, AsyncIterator

from agent_framework import ChatOptions, Message

# Trần token đủ rộng cho một bản tin/brief dài; chặn model "tràng giang" vô hạn.
DEFAULT_MAX_TOKENS = 3000

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    """Bỏ block <think>…</think>; xử lý cả trường hợp thiếu thẻ mở/đóng."""
    text = _THINK_RE.sub("", text)
    if _THINK_CLOSE in text:  # thẻ đóng lẻ (thẻ mở bị nuốt) → cắt phần trước nó
        text = text.split(_THINK_CLOSE, 1)[1]
    return text.strip()


def _options(max_tokens: int, temperature: float) -> ChatOptions:
    return ChatOptions(max_tokens=max_tokens, temperature=temperature)


async def complete_text(
    llm: Any,
    messages: list[Message],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.6,
) -> str:
    response = await llm.get_response(messages, options=_options(max_tokens, temperature))
    return _strip_think(str(getattr(response, "text", "") or ""))


async def stream_text(
    llm: Any,
    messages: list[Message],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.6,
) -> AsyncIterator[str]:
    """Stream delta text, ĐÃ lọc block <think> đầu output.

    State-machine: `unknown` (chưa biết có think) → `think` (đang suy luận, nuốt) |
    `pass` (đang trả lời, emit). Khi ở `unknown`, gom buffer tới khi đủ phân biệt
    output có bắt đầu bằng `<think>` hay không (tránh nhầm khi delta đầu chỉ là `<`).
    """
    stream = llm.get_response(messages, stream=True, options=_options(max_tokens, temperature))
    buffer = ""
    state = "unknown"
    async for update in stream:
        text = getattr(update, "text", "") or ""
        if not text:
            continue
        if state == "pass":
            yield text
            continue

        buffer += text
        if state == "unknown":
            stripped = buffer.lstrip()
            if not stripped:
                continue
            if stripped.startswith(_THINK_OPEN):
                state = "think"
            elif _THINK_OPEN.startswith(stripped):
                continue  # còn mơ hồ (vd "<th") — chờ thêm
            else:
                state = "pass"
                yield buffer
                buffer = ""
                continue

        if state == "think" and _THINK_CLOSE in buffer:
            after = buffer.split(_THINK_CLOSE, 1)[1].lstrip("\n")
            state = "pass"
            buffer = ""
            if after:
                yield after

    # Kết thúc mà vẫn chưa thoát think (think không đóng / chỉ có think) → cố vớt phần sạch.
    if state != "pass" and buffer:
        cleaned = _strip_think(buffer)
        if cleaned:
            yield cleaned
