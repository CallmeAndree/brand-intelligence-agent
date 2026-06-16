"""Hàm toán cụm dùng CHUNG giữa batch (`scripts/embed_cluster.py`) và gán cụm
incremental online (`AssignClustersUseCase`).

Tách ra một chỗ để hai đường (full-rebuild + incremental) không lệch logic
cosine / linkage / lọc từ khóa / đặt nhãn LLM.

Quyết định thuật toán (2026-06-15):
- Batch (chính xác nhất, nhìn toàn cục): **Agglomerative average-linkage trên cosine**
  + cắt theo `distance_threshold`. Average-linkage diệt đúng lỗi "chaining" của
  single-linkage (max-linkage) — nguyên nhân cụm rác kiểu "Không kỳ vọng" hút mọi
  cụm từ phủ định lại với nhau. Cụm quá nhỏ (< min_cluster_size) bị dồn về noise (-1).
- Online (1 mention/lần, realtime): khớp **average-linkage** (cosine trung bình tới
  TẤT CẢ member) thay vì max-linkage → vừa chống trôi centroid, vừa chống chaining.
- Trước khi gom keyword: **lọc bỏ từ khóa rỗng nghĩa** (phủ định/cảm thán thuần,
  không gắn danh từ sản phẩm) — đây là nguồn chính làm nhiễu nhóm từ khóa.
"""

from typing import Any

import numpy as np
from agent_framework import Message
from sklearn.cluster import AgglomerativeClustering

MAX_REPRESENTATIVES = 8
NOISE_CLUSTER_ID = -1

# Từ chức năng / cảm thán / phủ định tiếng Việt — KHÔNG mang thông tin sản phẩm.
# Một keyword chỉ gồm toàn các token này (vd "không nhanh", "chưa được", "không ổn",
# "chả được gì", "ảo quá", "nói không") là cảm xúc thuần → bỏ khỏi gom cụm từ khóa
# để không tạo cụm rác "Không kỳ vọng". Keyword còn ÍT NHẤT 1 token ngoài tập này
# (vd "liên kết cake", "không hiện cic", "kết quả game", "lên hạng khó") → GIỮ.
_GENERIC_TOKENS: frozenset[str] = frozenset(
    {
        "không", "chẳng", "chả", "chưa", "đâu", "đừng", "khỏi", "nỏ",
        "gì", "chi", "sao", "vậy", "thế", "nào", "đó", "này", "kia",
        "được", "bị", "nữa", "vẫn", "còn", "lại", "luôn", "mãi", "hoài", "rồi",
        "rất", "quá", "lắm", "hơi", "khá", "cực", "vô", "cùng", "thật", "thực",
        "nhanh", "chậm", "lâu", "dễ", "khó", "ổn", "tốt", "tệ", "dở", "kém", "ngon",
        "thấy", "rõ", "biết", "hiểu", "tin", "mong", "trông", "kỳ", "vọng", "ngờ",
        "làm", "ra", "vào", "lên", "xuống", "đi", "về", "tới", "đến", "nói", "bảo",
        "dùng", "xài", "ảo", "thật", "giả", "nhỉ", "ạ", "à", "ờ", "ừ", "hả",
        "nó", "mình", "tôi", "bạn", "họ", "ai", "người", "ta", "mày", "tao",
        "là", "có", "và", "với", "thì", "mà", "nên", "cho", "của", "ở", "tại",
        "y", "nguyên", "kịp", "may", "chắc", "hình", "như", "kiểu", "đại", "khái",
    }
)

# Keyword bị loại thẳng (cụm cảm thán/phủ định phổ biến, dù có token "lạ").
_JUNK_KEYWORDS: frozenset[str] = frozenset(
    {
        "không kỳ vọng", "không trông mong", "nhanh còn kịp", "ảo quá",
        "chả được gì", "nói không", "thoát ra vẫn y nguyên", "không làm gì",
    }
)


def cosine_normalize(matrix: np.ndarray) -> np.ndarray:
    """Chuẩn hoá L2 theo hàng; vector 0 giữ nguyên (norm=1) để khỏi chia 0."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def centroid(vectors: np.ndarray) -> np.ndarray:
    return vectors.mean(axis=0)


def nearest_representatives(
    values: list[str],
    vectors: np.ndarray,
    center: np.ndarray,
    limit: int = MAX_REPRESENTATIVES,
) -> list[str]:
    if not values:
        return []
    norm_vectors = cosine_normalize(vectors)
    norm_centroid = cosine_normalize(center.reshape(1, -1))[0]
    scores = norm_vectors @ norm_centroid
    order = np.argsort(-scores)[:limit]
    return [values[int(index)] for index in order]


def best_match(vec_norm: np.ndarray, centroids_norm: np.ndarray | None) -> tuple[int | None, float]:
    """Tìm centroid gần nhất (cosine) với 1 vector ĐÃ chuẩn hoá.

    `centroids_norm` là ma trận (n, d) đã chuẩn hoá theo hàng. Trả (index, score);
    (None, -1.0) khi chưa có centroid nào.
    """
    if centroids_norm is None or len(centroids_norm) == 0:
        return None, -1.0
    scores = centroids_norm @ vec_norm
    index = int(np.argmax(scores))
    return index, float(scores[index])


def clean_keyword(value: Any) -> str:
    return str(value).strip().lower()


def is_meaningful_keyword(keyword: str) -> bool:
    """True nếu keyword mang thông tin sản phẩm (đáng gom cụm); False nếu là
    cảm thán/phủ định thuần. Heuristic: bỏ nếu nằm trong junk-set, hoặc MỌI token
    đều thuộc tập từ chức năng/cảm thán, hoặc quá ngắn (≤2 ký tự)."""
    kw = clean_keyword(keyword)
    if len(kw) <= 2 or kw in _JUNK_KEYWORDS:
        return False
    tokens = [t for t in kw.split() if t]
    if not tokens:
        return False
    return any(token not in _GENERIC_TOKENS for token in tokens)


def agglomerative_labels(
    vectors: np.ndarray,
    distance_threshold: float,
    min_cluster_size: int = 2,
) -> np.ndarray:
    """Gom cụm bằng Agglomerative average-linkage trên cosine, cắt theo
    `distance_threshold` (= 1 - ngưỡng cosine). Số cụm TỰ SUY (n_clusters=None).
    Cụm nhỏ hơn `min_cluster_size` bị dồn về noise `-1` (không ép vào cụm khác).

    Đây là thuật toán gom cụm CHÍNH cho batch — average-linkage không bị chaining
    như single/max-linkage, không trôi centroid như centroid-linkage.
    """
    total = len(vectors)
    if total == 0:
        return np.array([], dtype=int)
    if total == 1:
        return np.zeros(1, dtype=int)

    normalized = cosine_normalize(vectors.astype(float))
    raw = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    ).fit_predict(normalized)

    # Dồn cụm nhỏ < min_cluster_size về noise -1, đánh số lại cụm hợp lệ từ 0.
    counts: dict[int, int] = {}
    for label in raw:
        counts[int(label)] = counts.get(int(label), 0) + 1
    remap: dict[int, int] = {}
    next_id = 0
    out = np.empty(total, dtype=int)
    for i, label in enumerate(raw):
        label = int(label)
        if counts[label] < min_cluster_size:
            out[i] = NOISE_CLUSTER_ID
            continue
        if label not in remap:
            remap[label] = next_id
            next_id += 1
        out[i] = remap[label]
    return out


async def label_cluster(llm: Any, kind: str, representatives: list[str]) -> str:
    """Đặt nhãn tiếng Việt ngắn cho một cụm qua LLM; fallback an toàn khi lỗi.

    Neo ngữ cảnh Zalopay + yêu cầu nhãn mô tả VẤN ĐỀ/CHỦ ĐỀ (không phải cảm xúc)
    để tránh nhãn vô nghĩa kiểu "Không kỳ vọng" / "Không lộ đường may".
    """
    if not representatives:
        return "Khác"
    prompt = (
        "Bối cảnh: đây là các phản ánh tiêu cực của người dùng về ví điện tử Zalopay. "
        f"Hãy đặt MỘT nhãn tiếng Việt ngắn gọn (tối đa 6 từ) gọi tên VẤN ĐỀ/CHỦ ĐỀ chung "
        f"của cụm {kind} dưới đây. Nhãn phải là danh từ/cụm danh từ mô tả nội dung sự việc "
        "(ví dụ: 'Trừ tiền sai', 'Nghi ngờ lừa đảo', 'Liên kết ngân hàng lỗi', 'Thăng hạng thành viên'), "
        "KHÔNG dùng câu cảm thán/phủ định, KHÔNG ghi 'Zalopay'. Chỉ trả về nhãn, không giải thích.\n"
        + "\n".join(f"- {item}" for item in representatives)
    )
    try:
        response = await llm.get_response([Message("user", [prompt])])
        text = getattr(response, "text", None) or getattr(response, "value", None) or str(response)
        return str(text).strip().strip('"')[:120] or "Khác"
    except Exception:
        return representatives[0][:120]
