import asyncio
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
from app.modules.alerting.domain.models import Department
from app.modules.alerting.domain.usecases.compose_brief import ComposeBriefUseCase
from app.modules.alerting.domain.usecases.route_department import RouteDepartmentUseCase
from app.modules.alerting.presentation.routes import router as alerting_router
from app.modules.clustering.data.cluster_repository import MongoClusterRepository
from app.modules.clustering.data.http_cluster_repository import HttpClusterRepository
from app.modules.clustering.domain.usecases.assign_clusters import AssignClustersUseCase
from app.modules.enrichment.data.worker import EnrichWorker
from app.modules.enrichment.domain.usecases.enrich_one import EnrichOneUseCase
from app.modules.generation.data.artifact_repository import MongoMonitorArtifactRepository
from app.modules.generation.data.cluster_context_builder import ClusterContextBuilder
from app.modules.generation.data.http_artifact_repository import HttpMonitorArtifactRepository
from app.modules.generation.domain.models import ArtifactType
from app.modules.generation.domain.usecases.generate import (
    GenerateBrandVoiceUseCase,
    GenerateContentUseCase,
    GenerateDesignBriefUseCase,
    GenerateNarrativeUseCase,
    GenerateResponsePlanUseCase,
    GenerateResponseStrategyUseCase,
    GenerateRootCauseUseCase,
    GenerateSeedingUseCase,
    ReviseBrandVoiceUseCase,
    ReviseNarrativeUseCase,
    ReviseResponseStrategyUseCase,
    ReviseRootCauseUseCase,
    ReviseSeedingUseCase,
)
from app.modules.generation.presentation.routes import router as generation_router
from app.modules.ingestion.data.http_mention_repository import HttpMentionRepository
from app.modules.ingestion.data.mention_repository import MentionDataRepository
from app.modules.ingestion.domain.repository import MentionRepo
from app.modules.ingestion.domain.usecases.ingest_email import IngestEmailUseCase
from app.modules.ingestion.presentation.routes import router as ingestion_router
from app.modules.query.data.http_query_repository import HttpQueryRepository
from app.modules.query.data.mongo_query_repository import MongoQueryRepository
from app.modules.query.domain.usecases.query_tools import (
    ComparePeriodsUseCase,
    GetClusterDetailUseCase,
    GetMentionsUseCase,
    GetTrendUseCase,
    SearchMentionsUseCase,
)
from app.modules.query.presentation.routes import router as query_router

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

    # Online incremental clustering chạy ở CẢ 2 repo mode: mongo (local) qua
    # MongoClusterRepository; http (runtime PUBLIC trên deploy) qua HttpClusterRepository
    # (đọc/ghi cụm qua data-backend) → cụm tự gom real-time mỗi mention kể cả khi deploy.
    cluster_assigner: AssignClustersUseCase | None = None
    cluster_repo_http: HttpClusterRepository | None = None
    if settings.incremental_clustering_enabled:
        if db is not None:
            _cluster_repo = MongoClusterRepository(db)
        else:
            cluster_repo_http = HttpClusterRepository(
                settings.data_backend_url, settings.data_backend_token
            )
            _cluster_repo = cluster_repo_http
        cluster_assigner = AssignClustersUseCase(
            repo=_cluster_repo,
            embed=embed_batch,
            llm=gemma_client,
            cluster_threshold=settings.cluster_cosine_threshold,
            keyword_threshold=settings.keyword_cosine_threshold,
        )

    # Auto-rebuild batch clustering sau mỗi ĐỢT ingest (debounce). Chỉ khi Mongo trực
    # tiếp (db not None / repo_mode=mongo) — batch cần Mongo trực tiếp. Worker báo qua
    # event mỗi khi enrich xong 1 mention; loop dưới gom cả đợt rồi chạy 1 lần.
    auto_rebuild = db is not None and settings.cluster_auto_rebuild_enabled
    cluster_rebuild_req: asyncio.Event = asyncio.Event()

    worker = EnrichWorker(
        repo,
        enrich_one,
        embed_batch,
        settings.worker_concurrency,
        retry_delay=settings.enrich_retry_delay_seconds,
        max_attempts=settings.enrich_max_attempts,
        assign_clusters=cluster_assigner.execute if cluster_assigner else None,
        on_enriched=cluster_rebuild_req.set if auto_rebuild else None,
    )
    worker.start()

    # Startup chịu lỗi: nếu data store (Mongo/backend) tạm thời chưa sẵn sàng,
    # container vẫn boot + /health 200 (yêu cầu cứng của AgentBase). Recovery sẽ
    # chạy lại ở lần restart sau.
    try:
        await repo.ensure_indexes()
        if cluster_assigner is not None:
            await cluster_assigner.repo.ensure_indexes()
        await worker.recover_pending()
    except Exception:
        logger.exception("Khởi tạo data store thất bại — app vẫn chạy, sẽ thử lại sau")

    # reload_centroids RE-EMBED lại toàn bộ keyword của mọi nhóm qua gateway → CHẬM khi
    # gateway bị 429 (retry 21s/lần). KHÔNG được block lifespan: AgentBase có deadline
    # khởi động (~80s) → quá hạn = SIGKILL → crash-loop → rollout không promote (đã gặp
    # trên deploy). Chạy NỀN sau khi app đã serve /health; incremental clustering degrade
    # an toàn tới khi centroid sẵn sàng (warm xong trong vài phút kể cả lúc gateway 429).
    if cluster_assigner is not None:
        async def _warm_centroids() -> None:
            try:
                await cluster_assigner.reload_centroids()
                logger.info("reload_centroids (nền) hoàn tất")
            except Exception:
                logger.exception("reload_centroids (nền) thất bại — sẽ thử lại lần restart sau")

        app.state.warm_centroids_task = asyncio.create_task(_warm_centroids())

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
    # Brand voice revise: ghép playbook brand_voice + brand_tone (như use case Monitor gốc)
    # + nhắc xuất các mục `### <tone>` để `_parse_variants` tách tab tone khi revise.
    brand_voice_revise_prompt = (
        f"{load_prompt('monitor/brand_voice')}\n\n## Hướng dẫn giọng điệu (tone)\n"
        f"{load_prompt('monitor/brand_tone')}\n\n"
        "QUAN TRỌNG: Mỗi tone là một mục bắt đầu bằng heading `### <tên tone>`, tiếp theo "
        "là nội dung phản hồi hoàn chỉnh cho tone đó. Tạo tối thiểu 3 tone."
    )
    # 3 skill chat (content/design_brief/response_plan) — ngữ cảnh tự do, dùng MINIMAX.
    # + 5 skill Monitor revise-từ-chat (dùng ĐÚNG playbook Monitor, ngữ cảnh tự do — không
    #   bắt buộc ClusterContext). Cùng map → /generate(/stream) chọn use case theo type.
    chat_generation_usecases = {
        ArtifactType.CONTENT: GenerateContentUseCase(
            llm=minimax_client,
            prompt=load_prompt("chat/content_writing"),
            prompt_file="chat/content_writing.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.CONTENT,
        ),
        ArtifactType.DESIGN_BRIEF: GenerateDesignBriefUseCase(
            llm=minimax_client,
            prompt=load_prompt("chat/design_brief"),
            prompt_file="chat/design_brief.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.DESIGN_BRIEF,
        ),
        ArtifactType.RESPONSE_PLAN: GenerateResponsePlanUseCase(
            llm=minimax_client,
            prompt=load_prompt("chat/response_plan"),
            prompt_file="chat/response_plan.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.RESPONSE_PLAN,
        ),
        ArtifactType.NARRATIVE: ReviseNarrativeUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/narrative_summary"),
            prompt_file="monitor/narrative_summary.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.NARRATIVE,
        ),
        ArtifactType.ROOT_CAUSE: ReviseRootCauseUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/root_cause"),
            prompt_file="monitor/root_cause.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.ROOT_CAUSE,
        ),
        ArtifactType.RESPONSE_STRATEGY: ReviseResponseStrategyUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/response_strategy"),
            prompt_file="monitor/response_strategy.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.RESPONSE_STRATEGY,
        ),
        ArtifactType.SEEDING_COMMENTS: ReviseSeedingUseCase(
            llm=minimax_client,
            prompt=load_prompt("monitor/seeding_comments"),
            prompt_file="monitor/seeding_comments.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.SEEDING_COMMENTS,
        ),
        ArtifactType.BRAND_VOICE: ReviseBrandVoiceUseCase(
            llm=minimax_client,
            prompt=brand_voice_revise_prompt,
            prompt_file="monitor/brand_voice.md",
            model_name=minimax_model_name,
            artifact_type=ArtifactType.BRAND_VOICE,
        ),
    }
    app.state.monitor_artifact_repo = artifact_repo
    app.state.cluster_context_builder = ClusterContextBuilder(
        reader=reader, top_n=settings.cluster_context_top_n
    )
    app.state.generation_usecases = generation_usecases
    app.state.chat_generation_usecases = chat_generation_usecases
    app.state.alert_repo = alert_repo
    # Điều phối alert theo bi_product_area → ĐÚNG 1 trong 3 phòng (KHÔNG còn fallback
    # Brand/PR; taxonomy đã bỏ "Others" → mọi mention vào 1 trong 9 mảng). Map ngữ nghĩa:
    #   TELCO   ← Telco
    #   LOYALTY ← Loyalty, Entertainment, Daily Life Service, OTA
    #   TRANSFER← Transfer, Bill, Binding, Financial Service
    telco_dept = Department(name="TELCO", email=settings.receive_telco_email or settings.receive_email or None)
    loyalty_dept = Department(name="LOYALTY", email=settings.receive_loyalty_email or settings.receive_email or None)
    transfer_dept = Department(name="TRANSFER", email=settings.receive_transfer_email or settings.receive_email or None)
    dept_routes = {
        "Telco": telco_dept,
        "Loyalty": loyalty_dept,
        "Entertainment": loyalty_dept,
        "Daily Life Service": loyalty_dept,
        "OTA": loyalty_dept,
        "Transfer": transfer_dept,
        "Bill": transfer_dept,
        "Binding": transfer_dept,
        "Financial Service": transfer_dept,
    }
    # Mảng không xác định (cụm trống / data cũ còn "Others") → mặc định TRANSFER (ví core).
    app.state.route_department_usecase = RouteDepartmentUseCase(
        routes=dept_routes, fallback=transfer_dept
    )
    # Alert brief = sinh text gửi đi (email routing) → dùng MINIMAX cho chất lượng.
    app.state.compose_brief_usecase = ComposeBriefUseCase(
        llm=minimax_client,
        prompt=load_prompt("alert/alert_brief"),
        model_name=minimax_model_name,
    )
    app.state.cluster_context_builder_for_alert = app.state.cluster_context_builder
    app.state.email_sender = EmailSender(settings)

    # ---- Tool catalog text-to-query (chat) — POST /query/{tool} ----
    if settings.repo_mode == "http":
        query_repo = HttpQueryRepository(settings.data_backend_url, settings.data_backend_token)
        closeables.append(query_repo)
    else:
        query_repo = MongoQueryRepository(db)  # type: ignore[arg-type]
    app.state.query_usecases = {
        "get_mentions": GetMentionsUseCase(query_repo),
        "get_trend": GetTrendUseCase(query_repo, critical_min=settings.critical_min),
        "get_cluster_detail": GetClusterDetailUseCase(
            query_repo, top_n=settings.cluster_context_top_n
        ),
        "compare_periods": ComparePeriodsUseCase(query_repo, critical_min=settings.critical_min),
        "search_mentions": SearchMentionsUseCase(query_repo, embed=embed_batch),
    }

    try:
        await artifact_repo.ensure_indexes()
        await alert_repo.ensure_indexes()
    except Exception:
        logger.exception("Tạo index monitor_artifacts/alerts thất bại — sẽ thử lại sau")

    # Alert CHỈ thủ công (nút "Alert ngay" → POST /alerts/manual). KHÔNG có scheduler
    # auto-alert: đã gỡ phần velocity/scan để mọi cảnh báo do người dùng chủ động phát.

    # ---- Debounce auto cluster rebuild (in-process, repo_mode=mongo) ----
    async def _cluster_rebuild_loop() -> None:
        from scripts.embed_cluster import rebuild_clusters

        while True:
            await cluster_rebuild_req.wait()
            # Debounce: gom cả đợt — chờ tới khi "yên" debounce_seconds (không có mention
            # mới enrich xong) thì mới chạy batch 1 lần.
            while True:
                cluster_rebuild_req.clear()
                try:
                    await asyncio.wait_for(
                        cluster_rebuild_req.wait(),
                        timeout=settings.cluster_rebuild_debounce_seconds,
                    )
                    continue  # có tín hiệu mới trong cửa sổ → tiếp tục chờ (gom)
                except asyncio.TimeoutError:
                    break
            # Guard: chỉ rebuild khi ĐỢT INGEST đã rút hết pending — tránh chạy batch giữa
            # chừng (cạnh tranh gateway, làm 429 tệ hơn) khi tải lớn/throttle. Còn pending
            # → bỏ lượt, chờ tín hiệu success kế tiếp (khi enrich xong sẽ tự re-arm).
            try:
                still_pending = await db["mentions"].count_documents({"status": "pending"})
            except Exception:
                still_pending = 0
            if still_pending > 0:
                logger.info("Auto cluster rebuild: hoãn — còn %d pending (đợi rút hết)", still_pending)
                continue
            try:
                logger.info("Auto cluster rebuild (debounce) — chạy batch embed_cluster")
                result = await rebuild_clusters(db, gemma_client, skip_backfill=False)
                logger.info("Auto cluster rebuild xong: %s", result)
                if cluster_assigner is not None:
                    await cluster_assigner.reload_centroids()  # đồng bộ centroid online
            except Exception:
                logger.exception("Auto cluster rebuild lỗi — bỏ qua đợt này")

    rebuild_task: asyncio.Task | None = None
    if auto_rebuild:
        rebuild_task = asyncio.create_task(_cluster_rebuild_loop())
        logger.info(
            "Auto cluster rebuild BẬT (debounce=%.0fs sau mỗi đợt ingest)",
            settings.cluster_rebuild_debounce_seconds,
        )

    try:
        yield
    finally:
        if rebuild_task is not None:
            rebuild_task.cancel()
            try:
                await rebuild_task
            except asyncio.CancelledError:
                pass
        await worker.stop()
        if cluster_repo_http is not None:
            await cluster_repo_http.aclose()
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
    app.include_router(query_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/prompts/chat-system")
    async def chat_system_prompt() -> dict[str, str]:
        """Persona analyst cho Runtime 2 (RT2 không import app/ → lấy qua HTTP, cache 1 lần).

        Public (không cần token): chỉ là chuỗi persona, không nhạy cảm. load_prompt
        đã cache lru → không đọc đĩa mỗi request.
        """
        return {"prompt": load_prompt("chat/system")}

    @app.get("/prompts/chat-explain")
    async def chat_explain_prompt() -> dict[str, str]:
        """Playbook explain cho Runtime 2 (data point dashboard → phân tích grounded).

        RT2 không import app/ → lấy qua HTTP, cache 1 lần. Public (chỉ là chuỗi prompt).
        """
        return {"prompt": load_prompt("chat/explain")}

    return app


app = create_app()
