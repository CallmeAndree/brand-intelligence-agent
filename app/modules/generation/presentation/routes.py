"""Routes module generation — sinh/đọc/duyệt artifact cho monitor workspace.

Guard `verify_runtime1_token` (header X-Runtime1-Token). DI lấy từ app.state:
- `cluster_context_builder`: build ClusterContext
- `generation_usecases`: dict ArtifactType → use case
- `monitor_artifact_repo`: MonitorArtifactRepo
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.auth import verify_runtime1_token
from app.core.response import StandardResponse, create_success_response
from app.modules.generation.domain.models import ArtifactStatus, ArtifactType, MonitorArtifact
from app.modules.generation.presentation.schemas import GenerateRequest

router = APIRouter(tags=["generation"], dependencies=[Depends(verify_runtime1_token)])


def _sse(event: str, data: dict) -> str:
    """Đóng gói một sự kiện SSE: dòng `event:` + `data:` JSON, kết bằng dòng trống."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/clusters/{cluster_id}/generate", response_model=StandardResponse[MonitorArtifact])
async def generate(
    cluster_id: int,
    payload: GenerateRequest,
    request: Request,
) -> StandardResponse[MonitorArtifact]:
    builder = request.app.state.cluster_context_builder
    usecases = request.app.state.generation_usecases
    repo = request.app.state.monitor_artifact_repo

    usecase = usecases.get(ArtifactType(payload.type))
    if usecase is None:
        raise HTTPException(status_code=400, detail=f"unknown artifact type: {payload.type}")

    ctx = await builder.build(cluster_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"cluster {cluster_id} không có dữ liệu")

    artifact = await usecase.execute(ctx)
    await repo.insert_draft(artifact)
    return create_success_response(artifact)


@router.post("/clusters/{cluster_id}/generate/stream")
async def generate_stream(
    cluster_id: int,
    payload: GenerateRequest,
    request: Request,
) -> StreamingResponse:
    """Sinh artifact dạng SSE — stream từng delta text về UI, lưu draft khi xong.

    Sự kiện: `meta` (type) → nhiều `delta` ({text}) → `done` ({artifact}) | `error`.
    """
    builder = request.app.state.cluster_context_builder
    usecases = request.app.state.generation_usecases
    repo = request.app.state.monitor_artifact_repo

    usecase = usecases.get(ArtifactType(payload.type))
    if usecase is None:
        raise HTTPException(status_code=400, detail=f"unknown artifact type: {payload.type}")

    ctx = await builder.build(cluster_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"cluster {cluster_id} không có dữ liệu")

    async def event_source():
        yield _sse("meta", {"type": payload.type, "cluster_id": cluster_id})
        chunks: list[str] = []
        try:
            async for delta in usecase.stream(ctx):
                chunks.append(delta)
                yield _sse("delta", {"text": delta})
            artifact = usecase.build(ctx, "".join(chunks))
            await repo.insert_draft(artifact)
            yield _sse("done", {"artifact": json.loads(artifact.model_dump_json(by_alias=True))})
        except Exception as exc:  # noqa: BLE001 — báo lỗi qua SSE, không nuốt im lặng
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"[:300]})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/clusters/{cluster_id}/artifacts", response_model=StandardResponse[list[MonitorArtifact]])
async def list_artifacts(
    cluster_id: int, request: Request
) -> StandardResponse[list[MonitorArtifact]]:
    repo = request.app.state.monitor_artifact_repo
    artifacts = await repo.find_by_cluster(cluster_id)
    return create_success_response(artifacts)


@router.post("/artifacts/{artifact_id}/{action}", response_model=StandardResponse[dict])
async def update_artifact(
    artifact_id: str, action: str, request: Request
) -> StandardResponse[dict]:
    mapping = {"approve": ArtifactStatus.APPROVED, "discard": ArtifactStatus.DISCARDED}
    new_status = mapping.get(action)
    if new_status is None:
        raise HTTPException(status_code=400, detail="action phải là approve|discard")

    repo = request.app.state.monitor_artifact_repo
    matched = await repo.set_status(artifact_id, new_status)
    if not matched:
        raise HTTPException(status_code=404, detail="artifact không tồn tại")
    return create_success_response({"id": artifact_id, "status": new_status.value})
