import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.db import MongoConnection
from app.core.llm import build_llm_client
from app.core.settings import get_settings
from app.modules.enrichment.data.worker import EnrichWorker
from app.modules.enrichment.domain.usecases.enrich_one import EnrichOneUseCase
from app.modules.ingestion.data.http_mention_repository import HttpMentionRepository
from app.modules.ingestion.data.mention_repository import MentionDataRepository
from app.modules.ingestion.domain.repository import MentionRepo
from app.modules.ingestion.domain.usecases.ingest_email import IngestEmailUseCase
from app.modules.ingestion.presentation.routes import router as ingestion_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    repo: MentionRepo
    if settings.repo_mode == "http":
        repo = HttpMentionRepository(settings.data_backend_url, settings.data_backend_token)
    else:
        db = await MongoConnection.connect(settings)
        repo = MentionDataRepository(db)

    enrich_one = EnrichOneUseCase(build_llm_client(settings))
    worker = EnrichWorker(repo, enrich_one, settings.worker_concurrency)
    worker.start()

    # Startup chịu lỗi: nếu data store (Mongo/backend) tạm thời chưa sẵn sàng,
    # container vẫn boot + /health 200 (yêu cầu cứng của AgentBase). Recovery sẽ
    # chạy lại ở lần restart sau.
    try:
        await repo.ensure_indexes()
        await worker.recover_pending()
    except Exception:
        logger.exception("Khởi tạo data store thất bại — app vẫn chạy, sẽ thử lại sau")

    app.state.mention_repo = repo
    app.state.enrich_worker = worker
    app.state.ingest_usecase = IngestEmailUseCase(repo=repo, enqueue=worker.enqueue)

    try:
        yield
    finally:
        await worker.stop()
        if isinstance(repo, HttpMentionRepository):
            await repo.aclose()
        await MongoConnection.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Brand Intelligence Agent", lifespan=lifespan)
    app.include_router(ingestion_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
