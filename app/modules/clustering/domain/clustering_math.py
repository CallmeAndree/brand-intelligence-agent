"""Hàm toán cụm dùng CHUNG giữa batch (`scripts/embed_cluster.py`) và gán cụm
incremental online (`AssignClustersUseCase`).

Tách ra một chỗ để hai đường (full-rebuild + incremental) không lệch logic
cosine / centroid / đặt nhãn LLM.
"""

from typing import Any

import numpy as np
from agent_framework import Message

MAX_REPRESENTATIVES = 8


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


async def label_cluster(llm: Any, kind: str, representatives: list[str]) -> str:
    """Đặt nhãn tiếng Việt ngắn cho một cụm qua LLM; fallback an toàn khi lỗi."""
    if not representatives:
        return "Khác"
    prompt = (
        "Đặt một nhãn tiếng Việt ngắn gọn (tối đa 7 từ) cho cụm "
        f"{kind} sau. Chỉ trả về nhãn, không giải thích.\n"
        + "\n".join(f"- {item}" for item in representatives)
    )
    try:
        response = await llm.get_response([Message("user", [prompt])])
        text = getattr(response, "text", None) or getattr(response, "value", None) or str(response)
        return str(text).strip().strip('"')[:120] or "Khác"
    except Exception:
        return representatives[0][:120]
