"""Routes module alerting — phát alert thủ công cho một cụm + đọc lịch sử.

POST /alerts/manual: build context → route phòng ban → brief LLM → gửi email →
lưu `alerts` (kind="manual"). GET /alerts: lịch sử. Guard X-Runtime1-Token.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import verify_runtime1_token
from app.core.response import StandardResponse, create_success_response
from app.modules.alerting.domain.models import Alert
from app.modules.alerting.presentation.schemas import ManualAlertRequest

router = APIRouter(prefix="/alerts", tags=["alerting"], dependencies=[Depends(verify_runtime1_token)])


@router.post("/manual", response_model=StandardResponse[Alert])
async def manual_alert(payload: ManualAlertRequest, request: Request) -> StandardResponse[Alert]:
    builder = request.app.state.cluster_context_builder_for_alert
    route_uc = request.app.state.route_department_usecase
    compose_uc = request.app.state.compose_brief_usecase
    sender = request.app.state.email_sender
    repo = request.app.state.alert_repo

    ctx = await builder.build(payload.cluster_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"cluster {payload.cluster_id} không có dữ liệu")

    department = route_uc.execute(ctx)
    brief_md = await compose_uc.execute(ctx, department)
    subject = f"[ZLP Alert] {department.name} — {ctx.label}"[:200]
    email = await sender.send(subject, brief_md)

    alert = Alert(
        _id=Alert.new_id(),
        cluster_id=ctx.cluster_id,
        department=department.name,
        severity_snapshot=ctx.severity_max,
        brief_md=brief_md,
        email=email,
        source_mention_ids=[m.id for m in ctx.top_mentions],
    )
    await repo.insert(alert)
    return create_success_response(alert)


@router.get("", response_model=StandardResponse[list[Alert]])
async def list_alerts(
    request: Request, limit: int = 50, since: str | None = None
) -> StandardResponse[list[Alert]]:
    repo = request.app.state.alert_repo
    alerts = await repo.find_recent(limit=min(max(limit, 1), 200), since=since)
    return create_success_response(alerts)
