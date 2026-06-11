"""data-backend — lớp HTTP đặt cạnh Mongo trên VM.

Chạy TRÊN VM dev-chatbot-01 (cùng mạng với Mongo 10.0.1.3:27037), expose ra ngoài
qua Cloudflare tunnel. Agent ở runtime PUBLIC gọi vào đây bằng HttpMentionRepository.

Tái dùng nguyên MentionDataRepository (PyMongo) → logic Mongo nằm DUY NHẤT một chỗ.
Bảo vệ bằng header X-Data-Token (so với DATA_BACKEND_TOKEN).
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException

from app.core.db import MongoConnection
from app.core.settings import get_settings
from app.modules.enrichment.domain.models import BiFields
from app.modules.ingestion.data.mention_repository import MentionDataRepository
from app.modules.ingestion.domain.models import Mention

logging.basicConfig(level=logging.INFO)


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

    @app.post("/repo/set-enrichment/{mention_id}", dependencies=guard)
    async def set_enrichment(mention_id: str, payload: dict) -> dict[str, str]:
        await app.state.repo.set_enrichment(mention_id, BiFields.model_validate(payload))
        return {"status": "ok"}

    @app.post("/repo/mark-failed/{mention_id}", dependencies=guard)
    async def mark_failed(mention_id: str, payload: dict) -> dict[str, str]:
        await app.state.repo.mark_failed(mention_id, payload.get("reason", ""))
        return {"status": "ok"}

    return app


app = create_app()
