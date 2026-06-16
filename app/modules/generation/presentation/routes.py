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
from app.modules.generation.presentation.schemas import ChatGenerateRequest, GenerateRequest

router = APIRouter(tags=["generation"], dependencies=[Depends(verify_runtime1_token)])

# 3 skill chat tự do (content/design_brief/response_plan) + 5 skill Monitor revise-từ-chat
# (narrative/root_cause/response_strategy/brand_voice/seeding_comments). Cả 8 đều đi
# /generate(/stream) qua `chat_generation_usecases` (ngữ cảnh tự do, KHÔNG bắt buộc
# ClusterContext). Type ngoài tập này → 400.
_CHAT_SKILL_TYPES = {
    ArtifactType.CONTENT,
    ArtifactType.DESIGN_BRIEF,
    ArtifactType.RESPONSE_PLAN,
    ArtifactType.NARRATIVE,
    ArtifactType.ROOT_CAUSE,
    ArtifactType.RESPONSE_STRATEGY,
    ArtifactType.BRAND_VOICE,
    ArtifactType.SEEDING_COMMENTS,
}


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

    artifact = await usecase.execute(ctx, payload.instruction)
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
            async for delta in usecase.stream(ctx, payload.instruction):
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


@router.post("/generate", response_model=StandardResponse[MonitorArtifact])
async def chat_generate(
    payload: ChatGenerateRequest,
    request: Request,
) -> StandardResponse[MonitorArtifact]:
    """Sinh nội dung từ chat (3 skill). Ngữ cảnh tự do + (tùy chọn) ClusterContext.

    Ghi `monitor_artifacts` với `created_by="chat"` + `session_id`. RT2 gọi vào đây
    (kèm X-Runtime1-Token), KHÔNG ghi Mongo trực tiếp.
    """
    if payload.type not in _CHAT_SKILL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"/generate chỉ nhận type: {[t.value for t in _CHAT_SKILL_TYPES]}",
        )

    usecases = request.app.state.chat_generation_usecases
    repo = request.app.state.monitor_artifact_repo
    usecase = usecases.get(ArtifactType(payload.type))
    if usecase is None:
        raise HTTPException(status_code=400, detail=f"unknown skill type: {payload.type}")

    context = payload.context or ""
    # Có cluster_id → dựng ClusterContext và chèn lên đầu ngữ cảnh (bám dẫn chứng cụm).
    if payload.cluster_id is not None:
        builder = request.app.state.cluster_context_builder
        ctx = await builder.build(payload.cluster_id)
        if ctx is not None:
            block = ctx.to_prompt_block()
            context = f"{block}\n\n{context}".strip() if context else block

    artifact = await usecase.execute(
        context,
        instruction=payload.instruction,
        cluster_id=payload.cluster_id,
        session_id=payload.session_id,
    )
    await repo.insert_draft(artifact)
    return create_success_response(artifact)


@router.post("/generate/stream")
async def chat_generate_stream(
    payload: ChatGenerateRequest,
    request: Request,
) -> StreamingResponse:
    """Bản SSE của `/generate` — stream từng delta nội dung skill chat, lưu draft khi xong.

    RT2 gọi vào (kèm X-Runtime1-Token) rồi forward delta về chat UI để skill cũng
    streaming như chat thường. Sự kiện: `meta` → nhiều `delta` ({text}) → `done`
    ({artifact}) | `error`. Ghi `monitor_artifacts` (created_by="chat") sau khi xong.
    """
    if payload.type not in _CHAT_SKILL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"/generate/stream chỉ nhận type: {[t.value for t in _CHAT_SKILL_TYPES]}",
        )

    usecases = request.app.state.chat_generation_usecases
    repo = request.app.state.monitor_artifact_repo
    usecase = usecases.get(ArtifactType(payload.type))
    if usecase is None:
        raise HTTPException(status_code=400, detail=f"unknown skill type: {payload.type}")

    context = payload.context or ""
    # Có cluster_id → dựng ClusterContext và chèn lên đầu ngữ cảnh (bám dẫn chứng cụm).
    if payload.cluster_id is not None:
        builder = request.app.state.cluster_context_builder
        ctx = await builder.build(payload.cluster_id)
        if ctx is not None:
            block = ctx.to_prompt_block()
            context = f"{block}\n\n{context}".strip() if context else block

    async def event_source():
        yield _sse("meta", {"type": payload.type, "cluster_id": payload.cluster_id})
        chunks: list[str] = []
        try:
            async for delta in usecase.stream(context, payload.instruction):
                chunks.append(delta)
                yield _sse("delta", {"text": delta})
            artifact = usecase.build(
                "".join(chunks), cluster_id=payload.cluster_id, session_id=payload.session_id
            )
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
