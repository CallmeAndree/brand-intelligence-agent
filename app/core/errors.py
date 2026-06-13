"""Phân loại lỗi dùng chung giữa domain (enrich_one) và worker.

Gateway MaaS trả 429 khi rate-limit. Lỗi này là TRANSIENT — không phải lỗi
dữ liệu/schema — nên cả hai tầng phải nhận diện được để: (1) enrich_one không
đốt thêm call fallback, (2) worker giữ pending + thử lại mãi, không mark_failed.
"""

from typing import Any

try:  # openai luôn có mặt (embedding client), nhưng vẫn phòng thủ
    from openai import RateLimitError as _OpenAIRateLimitError
except Exception:  # pragma: no cover
    _OpenAIRateLimitError = ()  # type: ignore[assignment]

_RATE_LIMIT_HINTS = ("rate limit", "rate_limit", "too many requests", "429")


def _status_code(exc: Any) -> Any:
    return getattr(exc, "status_code", None) or getattr(exc, "code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )


def is_rate_limit_error(exc: BaseException | None) -> bool:
    """True nếu exc (hoặc bất kỳ cause/context nào) là lỗi 429 rate-limit."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if _OpenAIRateLimitError and isinstance(current, _OpenAIRateLimitError):
            return True
        if _status_code(current) == 429:
            return True
        text = str(current).lower()
        if any(hint in text for hint in _RATE_LIMIT_HINTS):
            return True
        current = current.__cause__ or current.__context__
    return False
