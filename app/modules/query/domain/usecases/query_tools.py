"""5 use case build pipeline THUẦN cho tool catalog (whitelist).

Mỗi use case `@dataclass(frozen=True)`, nhận `repo: QueryRepo` (deps inject), method
`execute(params)` async → `ToolResult`. KHÔNG import FastAPI/PyMongo; chỉ build
filter/pipeline cố định từ params đã validate (Pydantic enum/limit). LLM KHÔNG hề
chèn được operator Mongo — đây là tầng an toàn (design D3).

`get_trend`/`compare_periods` kèm `EChartSpec` cho chart inline; các tool khác trả rows.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

import numpy as np

from app.modules.clustering.domain.clustering_math import cosine_normalize
from app.modules.query.domain.models import (
    ComparePeriodsParams,
    EChartSeries,
    EChartSpec,
    GetClusterDetailParams,
    GetMentionsParams,
    GetTrendParams,
    SearchMentionsParams,
    ToolResult,
)
from app.modules.query.domain.repository import QueryRepo

# Tập field mention trả về cho LLM/UI (KHÔNG kéo vector/body nặng).
_MENTION_PROJECTION = {
    "mention": 1,
    "platform": 1,
    "source": 1,
    "url": 1,
    "received_at": 1,
    "bi_topic": 1,
    "bi_product_area": 1,
    "bi_severity": 1,
    "bi_intent": 1,
    "bi_is_actionable": 1,
    "bi_summary_vi": 1,
    "cluster_id": 1,
    "cluster_label": 1,
}

# Trần số mention quét cosine in-memory cho search (chặn RAM/độ trễ — design Risks).
_SEARCH_SCAN_CAP = 4000


def _parse_day(value: str, *, end: bool) -> datetime:
    """Parse 'YYYY-MM-DD' → datetime đầu/cuối ngày (mirror aggregations.ts buildMatch)."""
    base = datetime.fromisoformat(value[:10])
    if end:
        return base.replace(hour=23, minute=59, second=59, microsecond=999000)
    return base.replace(hour=0, minute=0, second=0, microsecond=0)


def _date_range(frm: str, to: str) -> dict[str, datetime]:
    return {"$gte": _parse_day(frm, end=False), "$lte": _parse_day(to, end=True)}


def _metric_group(metric: str, critical_min: int) -> dict[str, Any]:
    """Biểu thức $group cho 1 metric (trả field `val`)."""
    if metric == "avg_severity":
        return {"val": {"$avg": "$bi_severity"}}
    if metric == "critical_count":
        return {
            "val": {"$sum": {"$cond": [{"$gte": ["$bi_severity", critical_min]}, 1, 0]}}
        }
    return {"val": {"$sum": 1}}  # volume


def _metric_label(metric: str) -> str:
    return {
        "volume": "Số mention",
        "avg_severity": "Avg Severity",
        "critical_count": "Số mention nghiêm trọng",
    }.get(metric, metric)


@dataclass(frozen=True)
class GetMentionsUseCase:
    repo: QueryRepo

    async def execute(self, p: GetMentionsParams) -> ToolResult:
        import re

        match: dict[str, Any] = {"status": "done", "received_at": _date_range(p.from_, p.to)}
        if p.platform:
            # `platform` lưu lẫn casing (facebook/Facebook/FaceBook); dashboard đã gom về nhãn
            # chuẩn (lowercase) nên value truyền xuống có thể khác casing với DB. Khớp
            # case-insensitive đúng-cả-chuỗi để get_mentions KHÔNG rỗng khi explain truyền nhãn
            # đã normalize (vd "Facebook" vẫn khớp doc lưu "facebook").
            match["platform"] = {"$regex": f"^{re.escape(p.platform)}$", "$options": "i"}
        if p.product_area:
            match["bi_product_area"] = p.product_area
        if p.intent:
            match["bi_intent"] = p.intent
        if p.actionable is not None:
            match["bi_is_actionable"] = p.actionable
        if p.cluster_id is not None:
            match["cluster_id"] = p.cluster_id
        if p.keyword_group_id is not None:
            # KeywordCloud hiển thị NHÃN nhóm từ khóa (vd "Lỗi liên kết tài khoản") — hiếm khi
            # là chuỗi nguyên văn trong text mention. Quan hệ thật: mention.keyword_group_ids
            # CHỨA id nhóm → lọc theo id (Mongo tự match phần tử mảng) để explain keyword
            # truy ĐÚNG mention thuộc nhóm thay vì text_contains literal (ra rỗng).
            match["keyword_group_ids"] = p.keyword_group_id
        if p.text_contains:
            # regex từ NGƯỜI build (không phải LLM-operator): escape để tránh injection regex.
            match["mention"] = {"$regex": re.escape(p.text_contains), "$options": "i"}
        sev: dict[str, int] = {}
        if p.severity_min is not None:
            sev["$gte"] = p.severity_min
        if p.severity_max is not None:
            sev["$lte"] = p.severity_max
        if sev:
            match["bi_severity"] = sev

        rows = await self.repo.find(
            "mentions",
            match,
            sort=[("received_at", -1)],
            limit=p.limit,
            projection=_MENTION_PROJECTION,
        )
        return ToolResult(rows=_clean_rows(rows), summary={"count": len(rows)})


@dataclass(frozen=True)
class GetTrendUseCase:
    repo: QueryRepo
    critical_min: int = 7

    async def execute(self, p: GetTrendParams) -> ToolResult:
        match = {"status": "done", "received_at": _date_range(p.from_, p.to)}
        group_id: dict[str, Any] = {
            "bucket": {"$dateTrunc": {"date": "$received_at", "unit": p.window}}
        }
        if p.group_by:
            field = "platform" if p.group_by == "platform" else "bi_product_area"
            group_id["g"] = f"${field}"

        pipeline = [
            {"$match": match},
            {"$group": {"_id": group_id, **_metric_group(p.metric, self.critical_min)}},
            {"$sort": {"_id.bucket": 1}},
        ]
        docs = await self.repo.aggregate("mentions", pipeline)

        # Trục thời gian = các bucket distinct (đã sort). Series = 1 (hoặc nhiều khi group_by).
        buckets: list[str] = []
        seen: set[str] = set()
        for d in docs:
            label = _bucket_label(d["_id"].get("bucket"))
            if label not in seen:
                seen.add(label)
                buckets.append(label)

        series_map: dict[str, dict[str, float]] = {}
        for d in docs:
            label = _bucket_label(d["_id"].get("bucket"))
            gkey = str(d["_id"].get("g")) if p.group_by else _metric_label(p.metric)
            series_map.setdefault(gkey, {})[label] = round(float(d.get("val") or 0), 2)

        series = [
            EChartSeries(name=name, data=[vals.get(b, 0) for b in buckets])
            for name, vals in series_map.items()
        ]
        title = f"{_metric_label(p.metric)} theo {p.window}"
        chart = EChartSpec(type="line", title=title, xAxis=buckets, series=series)
        total = round(sum(sum(s.data) for s in series), 2)
        return ToolResult(
            summary={"metric": p.metric, "window": p.window, "total": total, "buckets": len(buckets)},
            charts=[chart],
        )


@dataclass(frozen=True)
class GetClusterDetailUseCase:
    repo: QueryRepo
    top_n: int = 12

    async def execute(self, p: GetClusterDetailParams) -> ToolResult:
        cluster = await self.repo.find_one("topic_cluster", {"_id": p.cluster_id})
        mentions = await self.repo.find(
            "mentions",
            {"cluster_id": p.cluster_id, "status": "done"},
            sort=[("bi_severity", -1), ("received_at", -1)],
            limit=self.top_n,
            projection=_MENTION_PROJECTION,
        )
        artifacts = await self.repo.find(
            "monitor_artifacts",
            {"cluster_id": p.cluster_id, "status": {"$ne": "discarded"}},
            sort=[("created_at", -1)],
            limit=10,
            projection={"type": 1, "status": 1, "created_at": 1, "created_by": 1},
        )
        summary: dict[str, Any] = {"cluster_id": p.cluster_id}
        if cluster:
            summary.update(
                {
                    "label": cluster.get("label"),
                    "count": cluster.get("count"),
                    "severity_max": cluster.get("severity_max"),
                    "sample_topics": cluster.get("sample_topics") or [],
                }
            )
        summary["artifacts"] = _clean_rows(artifacts)
        return ToolResult(rows=_clean_rows(mentions), summary=summary)


@dataclass(frozen=True)
class ComparePeriodsUseCase:
    repo: QueryRepo
    critical_min: int = 7

    async def _metric_value(self, metric: str, frm: str, to: str) -> float:
        pipeline = [
            {"$match": {"status": "done", "received_at": _date_range(frm, to)}},
            {"$group": {"_id": None, **_metric_group(metric, self.critical_min)}},
        ]
        docs = await self.repo.aggregate("mentions", pipeline)
        return round(float(docs[0]["val"]), 2) if docs else 0.0

    async def execute(self, p: ComparePeriodsParams) -> ToolResult:
        a = await self._metric_value(p.metric, p.period_a.from_, p.period_a.to)
        b = await self._metric_value(p.metric, p.period_b.from_, p.period_b.to)
        delta = round(b - a, 2)
        pct = round((delta / a) * 100, 1) if a else None
        chart = EChartSpec(
            type="bar",
            title=f"{_metric_label(p.metric)}: kỳ A vs kỳ B",
            xAxis=["Kỳ A", "Kỳ B"],
            series=[EChartSeries(name=_metric_label(p.metric), data=[a, b])],
        )
        return ToolResult(
            summary={
                "metric": p.metric,
                "period_a": a,
                "period_b": b,
                "delta": delta,
                "delta_pct": pct,
            },
            charts=[chart],
        )


@dataclass(frozen=True)
class SearchMentionsUseCase:
    repo: QueryRepo
    embed: Callable[[list[str]], Awaitable[list[list[float]]]]
    scan_cap: int = _SEARCH_SCAN_CAP

    async def execute(self, p: SearchMentionsParams) -> ToolResult:
        vecs = await self.embed([p.query])
        if not vecs:
            return ToolResult(rows=[])
        qvec = cosine_normalize(np.array([vecs[0]], dtype=float))[0]

        proj = {**_MENTION_PROJECTION, "summary_embedding": 1}
        candidates = await self.repo.find(
            "mentions",
            {"status": "done", "summary_embedding": {"$exists": True}},
            sort=[("received_at", -1)],
            limit=self.scan_cap,
            projection=proj,
        )
        scored: list[tuple[float, dict[str, Any]]] = []
        mats, keep = [], []
        for doc in candidates:
            emb = doc.get("summary_embedding")
            if not emb:
                continue
            mats.append(emb)
            keep.append(doc)
        if not mats:
            return ToolResult(rows=[])
        norm = cosine_normalize(np.array(mats, dtype=float))
        scores = norm @ qvec
        order = np.argsort(-scores)[: p.limit]
        for i in order:
            doc = dict(keep[int(i)])
            doc.pop("summary_embedding", None)
            doc["_score"] = round(float(scores[int(i)]), 4)
            scored.append((doc["_score"], doc))
        return ToolResult(rows=_clean_rows([d for _, d in scored]), summary={"count": len(scored)})


def _bucket_label(value: Any) -> str:
    """Nhãn bucket thời gian từ giá trị $dateTrunc (datetime) → 'YYYY-MM-DD'."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)[:10]


def _clean_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chuẩn hoá _id→str + received_at→ISO cho JSON (StandardResponse serialize được)."""
    out = []
    for r in rows:
        d = dict(r)
        if "_id" in d:
            d["_id"] = str(d["_id"])
        ra = d.get("received_at")
        if isinstance(ra, datetime):
            d["received_at"] = ra.isoformat()
        ca = d.get("created_at")
        if isinstance(ca, datetime):
            d["created_at"] = ca.isoformat()
        out.append(d)
    return out
