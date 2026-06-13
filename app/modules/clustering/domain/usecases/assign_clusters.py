"""Gán cụm incremental online cho một mention vừa enrich+embed.

Use case này KHÔNG thuần (ghi Mongo qua repo + gọi LLM/embed) nhưng giữ toàn bộ
state cụm trong bộ nhớ (1 replica) để cosine brute-force numpy không phải query
Mongo mỗi mention. Worker bọc `execute()` trong `asyncio.Lock` nên các method ở
đây KHÔNG cần khoá riêng — chúng giả định được gọi tuần tự.

D3 — topic cluster: cosine(topic_vec, centroid) ≥ ngưỡng → nhập cụm + cập nhật
running-mean centroid/count/last_seen/severity_max; ngược lại tạo cụm mới (LLM nhãn).
D4 — keyword group: mỗi keyword distinct chưa thấy → embed 1 lần (cache vector),
gán vào group gần nhất ≥ ngưỡng hoặc tạo group mới (LLM nhãn). Khớp bằng
**max-linkage** (cosine tới MEMBER gần nhất, không phải centroid): centroid running-mean
trôi về mean toàn cục khi nhóm lớn (qwen3-embedding-8b baseline cao) → hút keyword bừa.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.core.logging_mixin import LoggerMixin
from app.modules.clustering.domain.clustering_math import (
    best_match,
    clean_keyword,
    cosine_normalize,
    label_cluster,
)
from app.modules.clustering.domain.models import Cluster, KeywordGroup
from app.modules.clustering.domain.repository import ClusterRepo
from app.modules.enrichment.domain.models import BiFields

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]

# Trong khi cụm còn đang hình thành (count nhỏ), mỗi lần có chủ đề mới gia nhập thì
# đặt LẠI nhãn từ toàn bộ sample_topics tích lũy — nhãn "thay đổi theo thời gian"
# để phản ánh nội dung thật, không kẹt ở nhãn của mention hạt giống. Vượt ngưỡng này
# cụm coi như đã ổn định → giữ nhãn cố định, khỏi tốn LLM call mỗi mention.
RELABEL_MAX_COUNT = 12

# Gateway embedding giới hạn batch tối đa 32 input/call → chunk khi re-embed lúc reload.
_EMBED_BATCH = 32


class AssignClustersUseCase(LoggerMixin):
    def __init__(
        self,
        repo: ClusterRepo,
        embed: EmbedFn,
        llm: Any,
        cluster_threshold: float,
        keyword_threshold: float,
    ) -> None:
        self.repo = repo
        self.embed = embed
        self.llm = llm
        self.cluster_threshold = cluster_threshold
        self.keyword_threshold = keyword_threshold

        # State cache (đồng bộ với Mongo). Index trong list khớp hàng matrix.
        self._clusters: list[Cluster] = []
        self._cluster_centroids: np.ndarray | None = None  # (n, d) đã chuẩn hoá
        self._keyword_groups: list[KeywordGroup] = []
        # Max-linkage: mỗi nhóm giữ ma trận (k_i, d) vector member ĐÃ chuẩn hoá, khớp
        # 1-1 thứ tự với self._keyword_groups. Match = cosine tới member gần nhất.
        self._kw_group_vecs: list[np.ndarray] = []
        self._keyword_vectors: dict[str, list[float]] = {}  # cache vector keyword distinct
        self._next_cluster_id = 0
        self._next_group_id = 0

    # ----- cache lifecycle -------------------------------------------------

    async def reload_centroids(self) -> None:
        """Nạp lại centroid từ Mongo (lúc startup + sau batch re-seed)."""
        self._clusters = await self.repo.load_clusters()
        self._cluster_centroids = self._build_matrix([c.centroid for c in self._clusters])
        self._next_cluster_id = max((c.id for c in self._clusters), default=-1) + 1

        self._keyword_groups = await self.repo.load_keyword_groups()
        self._next_group_id = max((g.id for g in self._keyword_groups), default=-1) + 1

        # Max-linkage cần vector TỪNG member → re-embed lại keyword của mọi nhóm
        # (centroid lưu trong Mongo không đủ). Chunk ≤ _EMBED_BATCH theo giới hạn gateway.
        self._keyword_vectors.clear()
        distinct = list(dict.fromkeys(kw for g in self._keyword_groups for kw in g.keywords))
        for start in range(0, len(distinct), _EMBED_BATCH):
            chunk = distinct[start : start + _EMBED_BATCH]
            for kw, vector in zip(chunk, await self.embed(chunk), strict=True):
                self._keyword_vectors[kw] = vector
        self._kw_group_vecs = [self._member_matrix(g) for g in self._keyword_groups]

        self.logger.info(
            "Nạp cache cụm: %d cụm chủ đề, %d nhóm từ khóa",
            len(self._clusters),
            len(self._keyword_groups),
        )

    @staticmethod
    def _build_matrix(vectors: list[list[float]]) -> np.ndarray | None:
        if not vectors:
            return None
        return cosine_normalize(np.array(vectors, dtype=float))

    def _member_matrix(self, group: KeywordGroup) -> np.ndarray | None:
        """Ma trận (k, d) vector member của 1 nhóm, đã chuẩn hoá — cho max-linkage."""
        vectors = [self._keyword_vectors[kw] for kw in group.keywords if kw in self._keyword_vectors]
        if not vectors:
            return None
        return cosine_normalize(np.array(vectors, dtype=float))

    # ----- main entrypoint -------------------------------------------------

    async def execute(self, mention_id: str, fields: BiFields, topic_vec: list[float]) -> None:
        now = datetime.now(timezone.utc)
        cluster_id, cluster_label = await self._assign_topic(fields, topic_vec, now)
        group_ids = await self._assign_keywords(fields)
        await self.repo.set_mention_clustering(
            mention_id, cluster_id, cluster_label, sorted(group_ids)
        )

    # ----- D3: topic cluster ----------------------------------------------

    async def _assign_topic(
        self, fields: BiFields, topic_vec: list[float], now: datetime
    ) -> tuple[int, str]:
        vec = np.array(topic_vec, dtype=float)
        norm = float(np.linalg.norm(vec)) or 1.0
        vec_norm = vec / norm
        index, score = best_match(vec_norm, self._cluster_centroids)
        severity = fields.bi_severity

        if index is not None and score >= self.cluster_threshold:
            cluster = self._clusters[index]
            new_count = cluster.count + 1
            new_centroid = (np.array(cluster.centroid, dtype=float) * cluster.count + vec) / new_count
            new_severity_max = cluster.severity_max
            if severity is not None and (cluster.severity_max is None or severity > cluster.severity_max):
                new_severity_max = severity
            new_samples = list(cluster.sample_topics)
            added_topic = (
                bool(fields.bi_topic)
                and fields.bi_topic not in new_samples
                and len(new_samples) < 8
            )
            if added_topic:
                new_samples.append(fields.bi_topic)
            # Cụm còn non + vừa có chủ đề mới → đặt lại nhãn theo tập tích lũy (nhãn tiến
            # hóa theo thời gian). Cụm đã lớn (count > ngưỡng) thì giữ nhãn để bớt LLM call.
            new_label = cluster.label
            if added_topic and new_count <= RELABEL_MAX_COUNT:
                new_label = await label_cluster(self.llm, "chủ đề", new_samples)
            updated = cluster.model_copy(
                update={
                    "label": new_label,
                    "centroid": new_centroid.tolist(),
                    "count": new_count,
                    "last_seen": now,
                    "severity_max": new_severity_max,
                    "sample_topics": new_samples,
                }
            )
            # Ghi Mongo TRƯỚC; chỉ commit cache khi thành công (tránh lệch nếu upsert raise).
            await self.repo.upsert_cluster(updated)
            self._clusters[index] = updated
            self._cluster_centroids[index] = cosine_normalize(new_centroid.reshape(1, -1))[0]
            return updated.id, updated.label

        # Không khớp → cụm mới (LLM nhãn), mention làm hạt giống.
        cluster_id = self._next_cluster_id
        label = await label_cluster(self.llm, "chủ đề", [fields.bi_topic] if fields.bi_topic else [])
        cluster = Cluster(
            id=cluster_id,
            label=label,
            centroid=vec.tolist(),
            count=1,
            first_seen=now,
            last_seen=now,
            severity_max=severity,
            sample_topics=[fields.bi_topic] if fields.bi_topic else [],
        )
        # Mongo trước, cache sau (gồm cả _next_cluster_id) để fail không bẩn cache.
        await self.repo.upsert_cluster(cluster)
        self._next_cluster_id += 1
        self._clusters.append(cluster)
        self._cluster_centroids = self._append_row(self._cluster_centroids, vec_norm)
        return cluster_id, label

    # ----- D4: keyword groups ---------------------------------------------

    async def _assign_keywords(self, fields: BiFields) -> set[int]:
        keywords: list[str] = []
        for raw in fields.bi_keywords or []:
            kw = clean_keyword(raw)
            if kw and kw not in keywords:
                keywords.append(kw)
        if not keywords:
            return set()

        # Gom keyword chưa từng embed vào 1 call embed (batch nhỏ).
        missing = [kw for kw in keywords if kw not in self._keyword_vectors]
        if missing:
            vectors = await self.embed(missing)
            for kw, vector in zip(missing, vectors, strict=True):
                self._keyword_vectors[kw] = vector

        group_ids: set[int] = set()
        for kw in keywords:
            vector = self._keyword_vectors.get(kw)
            if vector is None:
                continue
            group_ids.add(await self._assign_one_keyword(kw, vector))
        return group_ids

    async def _assign_one_keyword(self, keyword: str, vector: list[float]) -> int:
        vec = np.array(vector, dtype=float)
        norm = float(np.linalg.norm(vec)) or 1.0
        vec_norm = vec / norm

        # Max-linkage: chọn nhóm có MEMBER gần nhất (cosine cao nhất), không dùng centroid.
        best_index: int | None = None
        best_score = -1.0
        for gi, matrix in enumerate(self._kw_group_vecs):
            if matrix is None or len(matrix) == 0:
                continue
            score = float(np.max(matrix @ vec_norm))
            if score > best_score:
                best_score = score
                best_index = gi

        if best_index is not None and best_score >= self.keyword_threshold:
            group = self._keyword_groups[best_index]
            if keyword not in group.keywords:
                old_count = len(group.keywords)
                # centroid vẫn lưu (running-mean) cho batch script/dashboard, KHÔNG dùng để khớp.
                new_centroid = (np.array(group.centroid, dtype=float) * old_count + vec) / (old_count + 1)
                updated = group.model_copy(
                    update={
                        "centroid": new_centroid.tolist(),
                        "keywords": group.keywords + [keyword],
                    }
                )
                # Mongo trước, cache sau.
                await self.repo.upsert_keyword_group(updated)
                self._keyword_groups[best_index] = updated
                self._keyword_vectors[keyword] = vector
                self._kw_group_vecs[best_index] = self._append_row(
                    self._kw_group_vecs[best_index], vec_norm
                )
                return updated.id
            return group.id

        group_id = self._next_group_id
        label = await label_cluster(self.llm, "từ khóa", [keyword])
        group = KeywordGroup(id=group_id, label=label, keywords=[keyword], centroid=vec.tolist())
        # Mongo trước, cache sau (gồm cả _next_group_id).
        await self.repo.upsert_keyword_group(group)
        self._next_group_id += 1
        self._keyword_groups.append(group)
        self._keyword_vectors[keyword] = vector
        self._kw_group_vecs.append(vec_norm.reshape(1, -1))
        return group_id

    @staticmethod
    def _append_row(matrix: np.ndarray | None, row_norm: np.ndarray) -> np.ndarray:
        row = row_norm.reshape(1, -1)
        if matrix is None or len(matrix) == 0:
            return row
        return np.vstack([matrix, row])
