from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Gateway VNG MaaS (OpenAI-compatible) — 1 API_KEY + 1 BASE_URL dùng chung cho
    # mọi LLM call + embedding.
    api_key: str = Field(alias="API_KEY")
    base_url: str = Field(alias="BASE_URL")
    # Hai model LLM qua cùng gateway, chọn theo tác vụ (xem app/core/llm.py):
    #   GEMMA   — enrich (phân loại/trích xuất) + đặt nhãn cụm: volume cao, rẻ/nhanh.
    #   MINIMAX — sinh text chất lượng: 5 tính năng monitor (bắt buộc) + alert brief.
    gemma_model: str = Field(alias="GEMMA_MODEL")
    minimax_model: str = Field(alias="MINIMAX_MODEL")
    mongodb_uri: str = Field(default="", alias="MONGODB_URI")
    mongo_db: str = Field(default="brand_intel", alias="MONGO_DB")
    webhook_token: str = Field(alias="WEBHOOK_TOKEN")
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")
    enrich_retry_delay_seconds: float = Field(default=300.0, alias="ENRICH_RETRY_DELAY_SECONDS")
    enrich_max_attempts: int = Field(default=5, alias="ENRICH_MAX_ATTEMPTS")
    # Embedding qua CÙNG gateway (dùng api_key/base_url ở trên) — chỉ cần tên model.
    embedding_model: str = Field(
        default="greennode/greennode-embedding-large-1007", alias="EMBEDDING_MODEL"
    )
    # Số chiều vector embedding — đổi theo model (qwen3-embedding-8b=4096, bge-m3=1024).
    # Đổi model embedding PHẢI khớp số này + re-embed lại toàn bộ data cũ.
    embedding_dim: int = Field(default=4096, alias="EMBEDDING_DIM")

    # Gán cụm incremental online trong worker (sau enrich). Ngưỡng cosine quyết định
    # mention/keyword có nhập cụm gần nhất hay tạo cụm mới — calibrate trên data thật.
    # ⚠️ Ngưỡng PHỤ THUỘC model embedding: qwen3-embedding-8b có baseline cosine cao
    # (~0.74 giữa text khác nghĩa) → ngưỡng phải cao (0.82/0.83); bge-m3 cũ dùng 0.6/0.65.
    # Đo lại nếu đổi EMBEDDING_MODEL (within ~0.86 / across ~0.74 → cắt ở ~0.82-0.83).
    incremental_clustering_enabled: bool = Field(default=True, alias="INCREMENTAL_CLUSTERING_ENABLED")
    cluster_cosine_threshold: float = Field(default=0.82, alias="CLUSTER_COSINE_THRESHOLD")
    # Keyword khớp bằng max-linkage (member gần nhất) → ngưỡng cao hơn topic; 0.85 tách
    # sạch trên qwen3-embedding-8b (mô phỏng: ~31 nhóm, nhóm lớn nhất ~10, không snowball).
    keyword_cosine_threshold: float = Field(default=0.85, alias="KEYWORD_COSINE_THRESHOLD")
    # Tự động chạy batch clustering (embed_cluster) sau mỗi ĐỢT ingest — debounce: sau khi
    # 1+ mention enrich xong, chờ `debounce_seconds` "yên" (không có mention mới) rồi gom batch
    # 1 lần (gộp cả đợt). Chỉ chạy khi REPO_MODE=mongo (cần Mongo trực tiếp). Tắt bằng env.
    cluster_auto_rebuild_enabled: bool = Field(default=True, alias="CLUSTER_AUTO_REBUILD_ENABLED")
    cluster_rebuild_debounce_seconds: float = Field(default=60.0, alias="CLUSTER_REBUILD_DEBOUNCE_SECONDS")

    # Repository backend selection:
    #   "mongo" (default) — kết nối Mongo trực tiếp qua PyMongo (dev/VM local).
    #   "http"            — gọi data-backend qua HTTP (runtime PUBLIC trên AgentBase,
    #                        không chạm Mongo trực tiếp; đi qua Cloudflare tunnel).
    repo_mode: str = Field(default="mongo", alias="REPO_MODE")
    data_backend_url: str = Field(default="", alias="DATA_BACKEND_URL")
    data_backend_token: str = Field(default="", alias="DATA_BACKEND_TOKEN")
    # Whitelist collection được phép GHI qua facade insert-one/update-one. Facade lộ
    # public qua tunnel → chặn ghi tùy ý ngoài danh sách (trả 400). CSV trong env.
    data_backend_write_whitelist: str = Field(
        default="mentions,alerts,monitor_artifacts,topic_cluster,keyword_groups",
        alias="DATA_BACKEND_WRITE_WHITELIST",
    )

    # Token bảo vệ endpoint sinh/ghi của Runtime 1 (generation/alerting) — TÁCH khỏi
    # WEBHOOK_TOKEN (ingest) để có thể xoay vòng độc lập. Front-end proxy giấu token này.
    runtime1_api_token: str = Field(default="", alias="RUNTIME1_API_TOKEN")
    # Ngưỡng severity coi một cụm là "critical" (đồng bộ FE severity.ts). Mention
    # severity 1–10; cụm có severity_max ≥ ngưỡng này mới vào panel critical.
    critical_min: int = Field(default=7, alias="CRITICAL_MIN")
    # Số mention tối đa nhét vào ClusterContext khi sinh nội dung (cắt theo severity/recency)
    # — giữ prompt gọn, tránh phình token.
    cluster_context_top_n: int = Field(default=12, alias="CLUSTER_CONTEXT_TOP_N")

    # Email alert (manual) qua SMTP Gmail. Thiếu creds → alert vẫn lưu, email "skipped".
    # Creds chỉ ở .env/.env.deploy (KHÔNG commit). SEND_EMAIL = SMTP user = sender;
    # RECEIVE_EMAIL = recipient demo; EMAIL_APP_PASSWORD = Gmail app password.
    send_email: str = Field(default="", alias="SEND_EMAIL")
    receive_email: str = Field(default="", alias="RECEIVE_EMAIL")  # hộp chung / fallback
    email_app_password: str = Field(default="", alias="EMAIL_APP_PASSWORD")
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    # Điều phối alert về ĐÚNG phòng ban theo bi_product_area (manual & auto đều dùng):
    #   product_area "Telco"    → phòng TELCO    → RECEIVE_TELCO_EMAIL
    #   product_area "Loyalty"  → phòng LOYALTY  → RECEIVE_LOYALTY_EMAIL
    #   product_area "Transfer" → phòng TRANSFER → RECEIVE_TRANSFER_EMAIL
    # Các mảng khác → hộp chung RECEIVE_EMAIL. Thiếu email phòng → fallback RECEIVE_EMAIL.
    receive_telco_email: str = Field(default="", alias="RECEIVE_TELCO_EMAIL")
    receive_loyalty_email: str = Field(default="", alias="RECEIVE_LOYALTY_EMAIL")
    receive_transfer_email: str = Field(default="", alias="RECEIVE_TRANSFER_EMAIL")

    # (Auto-alert velocity ĐÃ GỠ — chỉ còn alert thủ công qua POST /alerts/manual.)

    # Memory AgentBase (Runtime 2). Optional khi chưa cấu hình → chat degrade về no-memory.
    memory_id: str = Field(default="", alias="MEMORY_ID")
    memory_strategy_id: str = Field(default="", alias="MEMORY_STRATEGY_ID")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
