"""Build `ClusterContext` từ `mentions` + `clusters` + `keyword_groups`.

Top N mention theo severity rồi recency (env CLUSTER_CONTEXT_TOP_N). Đọc qua
`Reader` (mongo trực tiếp hoặc http facade) → dùng được ở cả 2 REPO_MODE.
"""

from dataclasses import dataclass

from app.core.reader import Reader
from app.modules.generation.domain.models import ClusterContext, MentionRef


@dataclass(frozen=True)
class ClusterContextBuilder:
    reader: Reader
    top_n: int = 12

    async def build(self, cluster_id: int) -> ClusterContext | None:
        cluster = await self.reader.find_one("clusters", {"_id": cluster_id})

        top_docs = await self.reader.find(
            "mentions",
            {"cluster_id": cluster_id, "status": "done"},
            sort=[("bi_severity", -1), ("received_at", -1)],
            limit=self.top_n,
        )
        # Cụm chưa có cluster doc nhưng có mention → vẫn build từ mention.
        if cluster is None and not top_docs:
            return None

        top_mentions = [
            MentionRef(
                id=str(d.get("_id")),
                summary=d.get("bi_summary_vi") or (d.get("mention") or "")[:160] or None,
                severity=d.get("bi_severity"),
                intent=d.get("bi_intent"),
                product_area=d.get("bi_product_area"),
                platform=d.get("platform") or d.get("source"),
                received_at=d.get("received_at"),
                url=d.get("url"),
            )
            for d in top_docs
        ]

        # Nhãn nhóm từ khóa từ các mention thành viên (distinct keyword_group_ids).
        kw_ids: list[int] = []
        for d in top_docs:
            for gid in d.get("keyword_group_ids") or []:
                if gid not in kw_ids:
                    kw_ids.append(gid)
        keyword_groups: list[str] = []
        if kw_ids:
            groups = await self.reader.find("keyword_groups", {"_id": {"$in": kw_ids}})
            keyword_groups = [g.get("label", "") for g in groups if g.get("label")]

        label = (cluster or {}).get("label") or top_docs[0].get("cluster_label") or f"Cụm #{cluster_id}"
        severities = [d.get("bi_severity") for d in top_docs if d.get("bi_severity") is not None]
        sev_max = (cluster or {}).get("severity_max") or (max(severities) if severities else None)
        sev_avg = round(sum(severities) / len(severities), 1) if severities else None

        return ClusterContext(
            cluster_id=cluster_id,
            label=label,
            count=(cluster or {}).get("count") or len(top_docs),
            severity_max=sev_max,
            severity_avg=sev_avg,
            sample_topics=(cluster or {}).get("sample_topics") or [],
            keyword_groups=keyword_groups,
            top_mentions=top_mentions,
        )
