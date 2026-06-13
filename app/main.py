import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.logging_config import setup_logging
from app.core.db import MongoConnection
from app.core.embedding import build_embedding_client, embed_texts
from app.core.llm import build_gemma_client, build_minimax_client
from app.core.prompts import load_prompt
from app.core.reader import HttpReader, MongoReader
from app.core.settings import get_settings
from app.modules.alerting.data.alert_repository import MongoAlertRepository
from app.modules.alerting.data.email_sender import EmailSender
from app.modules.alerting.data.http_alert_repository import HttpAlertRepository
from app.modules.alerting.domain.usecases.compose_brief import ComposeBriefUseCase
from app.modules.alerting.domain.usecases.route_department import RouteDepartmentUseCase
from app.modules.alerting.presentation.routes import router as alerting_router
from app.modules.clustering.data.cluster_repository import MongoClusterRepository
from app.modules.clustering.domain.usecases.assign_clusters import AssignClustersUseCase
from app.modules.enrichment.data.worker import EnrichWorker
from app.modules.enrichment.domain.usecases.enrich_one import EnrichOneUseCase
from app.modules.generation.data.artifact_repository import MongoMonitorArtifactRepository
from app.modules.generation.data.cluster_context_builder import ClusterContextBuilder
from app.modules.generation.data.http_artifact_repository import HttpMonitorArtifactRepository
from app.modules.generation.domain.models import ArtifactType
from app.modules.generation.domain.usecases.generate import (
    GenerateBrandVoiceUseCase,
    GenerateNarrativeUseCase,
    GenerateResponseStrategyUseCase,
    GenerateRootCauseUseCase,
    GenerateSeedingUseCase,
)
from app.modules.generation.presentation.routes import router as generation_router
from app.modules.ingestion.data.http_mention_repository import HttpMentionRepository
from app.modules.ingestion.data.mention_repository import MentionDataRepository
from app.modules.ingestion.domain.repository import MentionRepo
from app.modules.ingestion.domain.usecases.ingest_email import IngestEmailUseCase
from app.modules.ingestion.presentation.routes import router as ingestion_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    repo: MentionRepo
    db = None
    if settings.repo_mode == "http":
        repo = HttpMentionRepository(settings.data_backend_url, settings.data_backend_token)
    else:
        db = await MongoConnection.connect(settings)
        repo = MentionDataRepository(db)

    embed_client = build_embedding_client(settings)

    async def embed_batch(texts: list[str]) -> list[list[float]]:
        return await embed_texts(embed_client, texts, settings)

    # GEMMA cho tác vụ volume cao (enrich + đặt nhãn cụm), MINIMAX cho sinh text.
    gemma_client = build_gemma_client(settings)
    minimax_client = build_minimax_client(settings)
    enrich_one = EnrichOneUseCase(gemma_client)

    # Gán cụm incremental chỉ khả dụng khi chạm Mongo trực tiếp (repo_mode=mongo).
    # Ở repo_mode=http (runtime PUBLIC qua data-backend) → tắt, vẫn dựa batch re-seed.
    cluster_assigner: AssignClustersUseCase | None = None
    if db is not None and settings.incremental_clustering_enabled:
        cluster_assigner = AssignClustersUseCase(
            repo=MongoClusterRepository(db),
            embed=embed_batch,
            llm=gemma_client,
            cluster_threshold=settings.cluster_cosine_threshold,
            keyword_threshold=settings.keyword_cosine_threshold,
        )

    worker = EnrichWorker(
        repo,
        enrich_one,
        embed_batch,
        settings.worker_concurrency,
        retry_delay=settings.enrich_retry_delay_seconds,
        max_attempts=settings.enrich_max_attempts,
        assign_clusters=cluster_assigner.execute if cluster_assigner else None,
    )
    worker.start()

    # Startup chịu lỗi: nếu data store (Mongo/backend) tạm thời chưa sẵn sàng,
    # container vẫn boot + /health 200 (yêu cầu cứng của AgentBase). Recovery sẽ
    # chạy lại ở lần restart sau.
    try:
        await repo.ensure_indexes()
        if cluster_assigner is not None:
            await cluster_assigner.repo.ensure_indexes()
            await cluster_assigner.reload_centroids()
        await worker.recover_pending()
    except Exception:
        logger.exception("Khởi tạo data store thất bại — app vẫn chạy, sẽ thử lại sau")

    app.state.mention_repo = repo
    app.state.enrich_worker = worker
    app.state.ingest_usecase = IngestEmailUseCase(repo=repo, enqueue=worker.enqueue)

    # ---- Monitor workspace: generation + manual alerting (nhánh A + B) ----
    # Reader/artifact-repo/alert-repo chọn theo REPO_MODE giống MentionRepo.
    closeables: list = []
    if settings.repo_mode == "http":
        reader = HttpReader(settings.data_backend_url, settings.data_backend_token)
        artifact_repo = HttpMonitorArtifactRepository(
            settings.data_backend_url, settings.data_backend_token
        )
        alert_repo = HttpAlertRepository(settings.data_backend_url, settings.data_backend_token)
        closeables += [reader, artifact_repo, alert_repo]
    else:
        reader = MongoReader(db)  # type: ignore[arg-type]
        artifact_repo = MongoMonitorArtifactRepository(db)  # type: ignore[arg-type]
        alert_repo = MongoAlertRepository(db)  # type: ignore[arg-type]

    # 5 tính năng sinh nội dung monitor BẮT BUỘC dùng MINIMAX (sinh text chất lượng).
    minimax_model_name = settings.minimax_model
    generation_usecases = {
        ArtifactType.NARRATIVE: GenerateNarrativeUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/narrative_summary"),
            prompt_file="monitor/narrative_summary.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.NARRATIVE,
        ),
        ArtifactType.ROOT_CAUSE: GenerateRootCauseUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/root_cause"),
            prompt_file="monitor/root_cause.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.ROOT_CAUSE,
        ),
        ArtifactType.RESPONSE_STRATEGY: GenerateResponseStrategyUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/response_strategy"),
            prompt_file="monitor/response_strategy.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.RESPONSE_STRATEGY,
        ),
        ArtifactType.SEEDING_COMMENTS: GenerateSeedingUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/seeding_comments"),
            prompt_file="monitor/seeding_comments.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.SEEDING_COMMENTS,
        ),
        ArtifactType.BRAND_VOICE: GenerateBrandVoiceUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/brand_voice"),
            tone_prompt=load_prompt("monitor/brand_tone"),
            prompt_file="monitor/brand_voice.md",
            model_name=minimax_model_name,
        ),
    }
    app.state.monitor_artifact_repo = artifact_repo
    app.state.cluster_context_builder = ClusterContextBuilder(
        reader=reader, top_n=settings.cluster_context_top_n
    )
    app.state.generation_usecases = generation_usecases
    app.state.alert_repo = alert_repo
    app.state.route_department_usecase = RouteDepartmentUseCase(
        rules=load_prompt("alert/department_routing")
    )
    # Alert brief = sinh text gửi đi (email routing) → dùng MINIMAX cho chất lượng.
    app.state.compose_brief_usecase = ComposeBriefUseCase(
        llm=minimax_client,
        prompt=load_prompt("alert/alert_brief"),
        model_name=minimax_model_name,
    )
    app.state.cluster_context_builder_for_alert = app.state.cluster_context_builder
    app.state.email_sender = EmailSender(settings)

    try:
        await artifact_repo.ensure_indexes()
        await alert_repo.ensure_indexes()
    except Exception:
        logger.exception("Tạo index monitor_artifacts/alerts thất bại — sẽ thử lại sau")

    try:
        yield
    finally:
        await worker.stop()
        if isinstance(repo, HttpMentionRepository):
            await repo.aclose()
        for c in closeables:
            aclose = getattr(c, "aclose", None)
            if aclose is not None:
                await aclose()
        await embed_client.close()
        await MongoConnection.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Brand Intelligence Agent", lifespan=lifespan)
    app.include_router(ingestion_router)
    app.include_router(generation_router)
    app.include_router(alerting_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
