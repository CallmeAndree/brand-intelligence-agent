"""Domain models cho tool catalog text-to-query (chat).

Params mỗi tool là Pydantic ĐÓNG (enum cho product_area/intent lấy từ enrichment,
limit có trần cứng) — đây là tầng whitelist: LLM CHỈ điền params, KHÔNG sinh query
Mongo. Use case build pipeline cố định từ params đã validate (xem usecases/).

`ToolResult` là shape trả về thống nhất: rows (mention/cluster), summary (số liệu),
charts (EChartSpec cho tool chuỗi thời gian). `EChartSpec` khớp contract FE.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.enrichment.domain.models import BiIntent, BiProductArea

# Trần cứng limit (chống LLM xin số lớn) — đồng bộ design D3.
MENTIONS_LIMIT_MAX = 50
SEARCH_LIMIT_MAX = 20

Metric = Literal["volume", "avg_severity", "critical_count"]
Window = Literal["day", "week", "month"]
GroupBy = Literal["platform", "product_area"]


class EChartSeries(BaseModel):
    name: str | None = None
    data: list[float]


class EChartSpec(BaseModel):
    """Chart tối giản khớp FE (lib/types EChartSpec). FE dựng option ECharts từ đây."""

    type: Literal["line", "bar"]
    title: str | None = None
    xAxis: list[str] | None = None
    series: list[EChartSeries]


class ToolResult(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    charts: list[EChartSpec] = Field(default_factory=list)


# ---- Params từng tool (whitelist) ----


class GetMentionsParams(BaseModel):
    from_: str = Field(alias="from")
    to: str
    platform: str | None = None
    severity_min: int | None = Field(default=None, ge=1, le=10)
    severity_max: int | None = Field(default=None, ge=1, le=10)
    product_area: BiProductArea | None = None
    intent: BiIntent | None = None
    actionable: bool | None = None
    cluster_id: int | None = None
    keyword_group_id: int | None = None
    text_contains: str | None = None
    limit: int = Field(default=20, ge=1, le=MENTIONS_LIMIT_MAX)

    model_config = {"populate_by_name": True}


class GetTrendParams(BaseModel):
    metric: Metric = "volume"
    window: Window = "week"
    from_: str = Field(alias="from")
    to: str
    group_by: GroupBy | None = None

    model_config = {"populate_by_name": True}


class GetClusterDetailParams(BaseModel):
    cluster_id: int


class Period(BaseModel):
    from_: str = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class ComparePeriodsParams(BaseModel):
    metric: Metric = "volume"
    period_a: Period
    period_b: Period


class SearchMentionsParams(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=SEARCH_LIMIT_MAX)
