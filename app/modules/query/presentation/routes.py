"""Routes tool catalog — POST /query/{tool} build pipeline whitelist an toàn.

Guard `verify_runtime1_token` (RT2 gọi vào kèm X-Runtime1-Token). LLM CHỈ điền params;
params validate Pydantic (enum product_area/intent, trần limit) → tham số ngoài enum
trả 422, không thực thi. Use case build pipeline cố định ở backend (không nhận operator
từ client). DI lấy `query_usecases` từ app.state.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import ValidationError

from app.core.auth import verify_runtime1_token
from app.core.response import StandardResponse, create_success_response
from app.modules.query.domain.models import (
    ComparePeriodsParams,
    GetClusterDetailParams,
    GetMentionsParams,
    GetTrendParams,
    SearchMentionsParams,
    ToolResult,
)

router = APIRouter(prefix="/query", tags=["query"], dependencies=[Depends(verify_runtime1_token)])

# tool → param model (whitelist 5 tool). Tool ngoài danh sách → 404.
_PARAM_MODELS = {
    "get_mentions": GetMentionsParams,
    "get_trend": GetTrendParams,
    "get_cluster_detail": GetClusterDetailParams,
    "compare_periods": ComparePeriodsParams,
    "search_mentions": SearchMentionsParams,
}


@router.post("/{tool}", response_model=StandardResponse[ToolResult])
async def run_tool(
    tool: str, request: Request, payload: dict = Body(default_factory=dict)
) -> StandardResponse[ToolResult]:
    model = _PARAM_MODELS.get(tool)
    if model is None:
        raise HTTPException(status_code=404, detail=f"unknown tool: {tool}")

    try:
        params = model.model_validate(payload)
    except ValidationError as exc:
        # Tham số ngoài enum / quá trần limit → 422, KHÔNG chạm DB.
        raise HTTPException(status_code=422, detail=exc.errors())

    usecase = request.app.state.query_usecases.get(tool)
    if usecase is None:
        raise HTTPException(status_code=503, detail=f"tool '{tool}' chưa sẵn sàng")

    result = await usecase.execute(params)
    return create_success_response(result)
