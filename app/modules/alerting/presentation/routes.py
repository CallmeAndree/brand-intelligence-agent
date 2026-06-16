"""Routes module alerting — phát alert THỦ CÔNG + đọc/ack lịch sử.

POST /alerts/manual: 1 cụm → route phòng ban → brief LLM → email đúng phòng → lưu.
POST /alerts/{id}/ack: đánh dấu đã đọc. GET /alerts: lịch sử. Guard X-Runtime1-Token.
(Không còn auto-alert velocity — mọi cảnh báo do người dùng chủ động phát.)
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
    # Điều phối: gửi đúng email phòng ban (department.email); thiếu → hộp chung.
    email = await sender.send(subject, brief_md, to=department.email)

    alert = Alert(
        _id=Alert.new_id(),
        kind="manual",
        cluster_id=ctx.cluster_id,
        department=department.name,
        severity_snapshot=ctx.severity_max,
        brief_md=brief_md,
        email=email,
        source_mention_ids=[m.id for m in ctx.top_mentions],
    )
    await repo.insert(alert)
    return create_success_response(alert)


@router.post("/{alert_id}/ack", response_model=StandardResponse[dict])
async def ack_alert(alert_id: str, request: Request) -> StandardResponse[dict]:
    repo = request.app.state.alert_repo
    ok = await repo.ack(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"alert {alert_id} không tồn tại")
    return create_success_response({"alert_id": alert_id, "acknowledged": True})


@router.get("", response_model=StandardResponse[list[Alert]])
async def list_alerts(
    request: Request, limit: int = 50, since: str | None = None
) -> StandardResponse[list[Alert]]:
    repo = request.app.state.alert_repo
    alerts = await repo.find_recent(limit=min(max(limit, 1), 200), since=since)
    return create_success_response(alerts)
