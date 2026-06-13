"""Prompt loader — đọc playbook `.md` từ `app/prompts/**` lúc chạy (cache nhẹ).

Tách prompt ra file `.md` để marketing/PR sửa nội dung mà KHÔNG đụng code. Tên prompt
là đường dẫn tương đối (không đuôi) dưới `app/prompts`, ví dụ `monitor/narrative_summary`
hoặc `alert/alert_brief`. Cache bằng dict để tránh đọc đĩa mỗi lần gọi LLM.
"""

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=128)
def load_prompt(name: str) -> str:
    """Đọc nội dung playbook `app/prompts/<name>.md`.

    `name` dùng dấu `/` cho thư mục con (vd "monitor/narrative_summary"). Ném
    FileNotFoundError với thông báo rõ nếu thiếu file (lỗi cấu hình, không nuốt).
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy playbook prompt: {path}")
    return path.read_text(encoding="utf-8").strip()


def format_prompt(name: str, /, **variables: object) -> str:
    """Đọc playbook rồi thay biến `{ten_bien}` an toàn.

    Dùng `str.format_map` với dict bỏ-qua-thiếu để một biến vắng không làm vỡ
    toàn bộ prompt (giữ literal `{x}` thay vì KeyError). Playbook tự do dùng cặp
    ngoặc `{}` cho ví dụ JSON nếu escape `{{`/`}}` theo cú pháp format chuẩn.
    """
    template = load_prompt(name)
    return template.format_map(_SafeDict(variables))


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # noqa: D401 — giữ literal khi thiếu biến
        return "{" + key + "}"
