"""data-backend — lớp HTTP đặt cạnh Mongo trên VM.

Chạy TRÊN VM dev-chatbot-01 (cùng mạng với Mongo 10.0.1.3:27037), expose ra ngoài
qua Cloudflare tunnel. Agent ở runtime PUBLIC gọi vào đây bằng HttpMentionRepository.

Tái dùng nguyên MentionDataRepository (PyMongo) → logic Mongo nằm DUY NHẤT một chỗ.
Bảo vệ bằng header X-Data-Token (so với DATA_BACKEND_TOKEN).
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from bson import json_util
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response

from app.core.db import MongoConnection
from app.core.logging_config import setup_logging
from app.core.settings import get_settings
from app.modules.ingestion.data.mention_repository import MentionDataRepository
from app.modules.ingestion.domain.models import Mention

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    db = await MongoConnection.connect(settings)
    repo = MentionDataRepository(db)
    await repo.ensure_indexes()
    app.state.repo = repo
    try:
        yield
    finally:
        await MongoConnection.close()


def _verify_token(x_data_token: str = Header(default="")) -> None:
    settings = get_settings()
    if not settings.data_backend_token or x_data_token != settings.data_backend_token:
        raise HTTPException(status_code=401, detail="invalid data token")


def create_app() -> FastAPI:
    app = FastAPI(title="BI Agent data-backend", lifespan=lifespan)
    guard = [Depends(_verify_token)]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/repo/ensure-indexes", dependencies=guard)
    async def ensure_indexes() -> dict[str, str]:
        await app.state.repo.ensure_indexes()
        return {"status": "ok"}

    @app.post("/repo/upsert", dependencies=guard)
    async def upsert(payload: dict) -> dict[str, str]:
        await app.state.repo.upsert(Mention.model_validate(payload))
        return {"status": "ok"}

    @app.get("/repo/get/{mention_id}", dependencies=guard)
    async def get(mention_id: str) -> dict:
        mention = await app.state.repo.get(mention_id)
        if mention is None:
            raise HTTPException(status_code=404, detail="not found")
        return mention.model_dump(by_alias=True, mode="json")

    @app.get("/repo/pending-ids", dependencies=guard)
    async def pending_ids() -> dict[str, list[str]]:
        return {"ids": await app.state.repo.find_pending_ids()}

    @app.get("/repo/failed-ids", dependencies=guard)
    async def failed_ids() -> dict[str, list[str]]:
        return {"ids": await app.state.repo.find_failed_ids()}

    @app.post("/repo/save-partial/{mention_id}", dependencies=guard)
    async def save_partial(mention_id: str, payload: dict) -> dict[str, str]:
        await app.state.repo.save_partial(mention_id, payload)
        return {"status": "ok"}

    @app.post("/repo/mark-enriched/{mention_id}", dependencies=guard)
    async def mark_enriched(mention_id: str) -> dict[str, str]:
        await app.state.repo.mark_enriched(mention_id)
        return {"status": "ok"}

    @app.post("/repo/mark-failed/{mention_id}", dependencies=guard)
    async def mark_failed(mention_id: str, payload: dict) -> dict[str, str]:
        await app.state.repo.mark_failed(mention_id, payload.get("reason", ""))
        return {"status": "ok"}

    # ---- Read-only facade cho front-end (Vercel) đọc Mongo qua tunnel ----
    # Front-end build $match/pipeline phía nó rồi gửi sang đây. Body & response
    # dùng Extended JSON (bson.json_util) để giữ kiểu Date/ObjectId/int qua HTTP
    # — relaxed JSON sẽ biến Date thành string làm hỏng truy vấn range thời gian.
    def _read_collection(spec: dict):
        db = MongoConnection.get_db()
        return db[spec.get("collection", "mentions")]

    @app.post("/repo/aggregate", dependencies=guard)
    async def aggregate(request: Request) -> Response:
        spec = json_util.loads((await request.body()).decode())
        coll = _read_collection(spec)
        docs = [doc async for doc in await coll.aggregate(spec.get("pipeline", []))]
        return Response(content=json_util.dumps(docs), media_type="application/json")

    @app.post("/repo/find", dependencies=guard)
    async def find(request: Request) -> Response:
        spec = json_util.loads((await request.body()).decode())
        coll = _read_collection(spec)
        cursor = coll.find(spec.get("filter", {}), spec.get("projection") or None)
        if spec.get("sort"):
            cursor = cursor.sort(list(spec["sort"].items()))
        if spec.get("skip"):
            cursor = cursor.skip(int(spec["skip"]))
        if spec.get("limit"):
            cursor = cursor.limit(int(spec["limit"]))
        docs = [doc async for doc in cursor]
        return Response(content=json_util.dumps(docs), media_type="application/json")

    @app.post("/repo/count", dependencies=guard)
    async def count(request: Request) -> dict[str, int]:
        spec = json_util.loads((await request.body()).decode())
        coll = _read_collection(spec)
        return {"count": await coll.count_documents(spec.get("filter", {}))}

    # ---- Write facade (generation/alerting Runtime 1 qua REPO_MODE=http) ----
    # Chỉ chấp nhận collection trong whitelist — facade public qua tunnel, KHÔNG mở
    # ghi tùy ý. EJSON body giữ kiểu Date/ObjectId qua HTTP (giống các route đọc).
    def _write_collection(spec: dict):
        name = spec.get("collection", "")
        whitelist = {
            c.strip()
            for c in get_settings().data_backend_write_whitelist.split(",")
            if c.strip()
        }
        if name not in whitelist:
            raise HTTPException(status_code=400, detail=f"collection '{name}' not writable")
        return MongoConnection.get_db()[name]

    @app.post("/repo/insert-one", dependencies=guard)
    async def insert_one(request: Request) -> Response:
        spec = json_util.loads((await request.body()).decode())
        coll = _write_collection(spec)
        result = await coll.insert_one(spec.get("doc", {}))
        return Response(
            content=json_util.dumps({"inserted_id": result.inserted_id}),
            media_type="application/json",
        )

    @app.post("/repo/update-one", dependencies=guard)
    async def update_one(request: Request) -> dict[str, int]:
        spec = json_util.loads((await request.body()).decode())
        coll = _write_collection(spec)
        result = await coll.update_one(
            spec.get("filter", {}),
            spec.get("update", {}),
            upsert=bool(spec.get("upsert", False)),
        )
        return {
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
        }

    return app


app = create_app()
