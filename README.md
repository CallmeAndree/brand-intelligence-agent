# Zalopay 505 — Brand Intelligence Agent

> AI agent theo dõi & phân tích các **mention tiêu cực** về **Zalopay (ZLP)** trên mạng xã hội, deploy trên nền tảng **GreenNode AgentBase**. Sản phẩm dự thi **Claw-a-thon 2026** (hackathon AI nội bộ VNG, tổ chức bởi GreenNode).

> ⚠️ **Phạm vi thương hiệu — CHỈ Zalopay/ZLP** (ví điện tử). KHÔNG bao gồm **Zalo** (app chat là sản phẩm khác của VNG).

---

## 1. Vấn đề & Use-case

Đội Brand/CSKH của Zalopay nhận hàng nghìn mention tiêu cực mỗi tháng từ social listening (Kompa, crawler...). Việc đọc thủ công không kịp: không biết **chủ đề nào đang nóng**, **mảng sản phẩm nào bị phàn nàn nhất**, **đâu là dấu hiệu khủng hoảng**, và mỗi lần cần báo cáo/soạn phản hồi lại mất nhiều giờ.

**Agent giải quyết bằng mục tiêu kép:**

- **(a) PULL — Hiểu & báo cáo (cho team nội bộ).** Tự động phân loại, chấm mức nghiêm trọng (severity), gom cụm chủ đề, và trả lời câu hỏi phân tích bằng ngôn ngữ tự nhiên kèm số liệu/biểu đồ thật.
- **(b) PUSH — Phát hiện & xử lý.** Theo dõi các cụm critical, một-chạm route cảnh báo tới **đúng phòng ban** qua email, và sinh sẵn **nội dung phản hồi** (báo cáo diễn biến, phân tích nguyên nhân, chiến lược, brand voice, seeding) để xử lý nhanh.

**Các kịch bản tiêu biểu:**

| Vai trò | Tình huống | Agent làm gì |
| --- | --- | --- |
| Brand Manager | "Tháng 1/2026 severity vọt lên — vì sao?" | Chuột phải điểm dữ liệu trên dashboard → Chat tự truy mention thật của tháng đó và **giải thích trên dữ liệu** (chủ đề, mẫu mention, gợi ý theo dõi). |
| Analyst | "So lượng mention critical tuần này vs tuần trước" | Chat gọi tool truy vấn → trả lời kèm **biểu đồ inline**. |
| Crisis team | Một cụm "Trừ tiền sai" tăng đột biến | Mở Monitor → "Alert ngay" route email tới phòng phụ trách + sinh draft phản hồi → "Gửi sang Chat" để **chỉnh lại theo prompt**. |

> **Use-case (≤300 ký tự — tiêu chí Claw-a-thon):**
> Agent theo dõi mention tiêu cực về Zalopay trên mạng xã hội: tự phân loại + chấm severity + gom cụm chủ đề; cung cấp dashboard, chat analyst trả lời kèm số liệu/biểu đồ, phát hiện cụm critical → route cảnh báo email đúng phòng ban và sinh nội dung phản hồi.

---

## 2. Tính năng chính

Front-end Next.js gồm **3 tab**:

- **Dashboard** — KPI + biểu đồ tương tác (timeline severity, phân bố nền tảng, top chủ đề/cụm, keyword cloud, top mảng sản phẩm, **Ma trận ưu tiên** volume × severity). Click để lọc chéo; **chuột phải bất kỳ điểm dữ liệu → "Giải thích"** sang Chat.
- **Monitor** — danh sách **cụm critical** + workspace **5 skill sinh nội dung AI** (báo cáo diễn biến / nguyên nhân / chiến lược ứng phó / brand voice / seeding); duyệt–tái sinh artifact; **"Alert ngay"** (gửi email thật tới đúng phòng) và **"Gửi sang Chat"** để revise.
- **Chat Analyst** — hội thoại streaming, có **working memory**, **text-to-query** (5 công cụ truy vấn dữ liệu thật), **biểu đồ inline**, và lịch sử hội thoại.

---

## 3. Kiến trúc & luồng dữ liệu

```
Email.json (dump) / webhook
        │
        ▼
  INGEST  ──►  lưu raw status=pending (Mongo)  ──►  asyncio.Queue
        │
        ▼
  WORKER  ──►  enrich_one (3-pass: topic → judgment → summary, GEMMA)
        │        + embedding (qwen3, gateway) + gán cụm online incremental
        ▼
  bi_* $set ngược vào document (idempotent), status=done
        │
        ├──► (a) Next.js: Dashboard + Chat Analyst (tool-calling + skill)
        └──► (b) Monitor: cụm critical → alert email + sinh nội dung phản hồi
```

**Nguyên tắc cốt lõi:**
1. **Tách logic enrich khỏi thời điểm gọi** — một hàm thuần `enrich_one(record) -> bi_*` dùng chung cho backfill lịch sử và on-ingest realtime.
2. **Lưu raw TRƯỚC, enrich SAU** — ingest không bao giờ nghẽn vì LLM; `status` là checkpoint tự nhiên cho recovery.
3. **Một data store duy nhất — MongoDB** — mọi tầng đọc/ghi cùng collection.

### Phân loại (taxonomy đã chốt)
- `bi_product_area`: **9 dòng sản phẩm Zalopay** — Transfer · Bill · OTA · Telco · Binding · Financial Service · Loyalty · Daily Life Service · Entertainment.
- `bi_intent`: 7 giá trị (khiếu nại, hỏi/hỗ trợ, cảnh báo/tố cáo, mỉa mai, so sánh đối thủ, góp ý, spam).
- `bi_severity` (1–10) + `bi_severity_factors` (7 tiêu chí rủi ro) + **escalation floor** tất định.
- `bi_topic` open-vocab → gom cụm ngữ nghĩa (embedding + average-linkage).

---

## 4. Tech stack & quyết định kỹ thuật

| Lớp | Công nghệ |
| --- | --- |
| Backend | Python + **FastAPI**, Clean Architecture 3-tier |
| Data store | **MongoDB** Community (VM, không Atlas) — store duy nhất |
| Queue/Worker | in-process **`asyncio.Queue`** + `Semaphore` (không Celery/Redis) |
| LLM (1 gateway, 2 model) | **GEMMA** (`google/gemma-4-31b-it`) cho enrich + đặt nhãn cụm; **MINIMAX** (`minimax/minimax-m2.5`) cho sinh nội dung + chat |
| Embedding | **`qwen/qwen3-embedding-8b`** (4096-dim) qua gateway; so khớp numpy cosine in-memory |
| Front-end | **Next.js** (App Router + TS + Tailwind + ECharts) |
| Deploy | **GreenNode AgentBase** (Custom Agent runtime) |

---

## 5. Topology triển khai (khác docker-compose local)

| Thành phần | Vai trò | Deploy |
| --- | --- | --- |
| **Runtime 1** (`app/`) | ingest + enrich + clustering + generation + alerting | AgentBase, PUBLIC, port 8080, `--min/max-replicas 1` (worker in-process) |
| **Runtime 2** (`agent/`) | Chat Analyst (AgentBase SDK, `POST /invocations`) | AgentBase, stateless, autoscale |
| **data_backend** (`data_backend/`) | facade `/repo/*` cạnh Mongo (auth token) | Cạnh Mongo trên VM, expose qua Cloudflare quick tunnel |
| **MongoDB** | data store | Community trên VM (không Atlas) |
| **Front-end** (`frontend/`) | Dashboard + Monitor + Chat | Local cho demo (hoặc Vercel qua tunnel) |

> Runtime 2 gọi Runtime 1 qua HTTP (`RUNTIME1_BASE_URL` + token) cho tool/skill/persona — RT2 không import `app/`.

---

## 6. Cấu trúc repo

| Thư mục | Vai trò |
| --- | --- |
| [`brand-intelligence-agent/`](brand-intelligence-agent/) | **Sản phẩm chính** — `app/` (RT1) · `agent/` (RT2) · `data_backend/` · `frontend/` · `scripts/` · `social-listening/` |
| [`__document__/`](__document__/) | Tài liệu kiến trúc/luồng/deploy (xem [STATUS.md](__document__/STATUS.md) để nắm nhanh hiện trạng) |
| [`openspec/`](openspec/) | Workflow spec-driven (changes + specs) |
| [`design/`](design/DESIGN.md) | Design system "Clay" cho front-end |
| [`Data/`](Data/) | Dataset gốc (5.790 email mention 06/2023–06/2026) |
| [`greennode-agentbase-skills/`](greennode-agentbase-skills/) | Skill vận hành lifecycle AgentBase |
| [`Rulebook.md`](Rulebook.md) | Thể lệ Claw-a-thon 2026 |

---

## 7. Chạy nhanh (dev/demo local)

```bash
cd brand-intelligence-agent
make up            # docker compose: mongo(27037) + app(8090) + data-backend(8091) + agent(8092)
make down / rebuild / logs
pytest             # test

# nạp dataset gốc vào pipeline
python scripts/replay_email.py        # POST Email.json → /ingest/email

# front-end
cd frontend && npm install && npm run dev
```

**Deploy AgentBase:**
```bash
make creds → make cf-tunnel → make deploy        # (deploy-r1 / deploy-r2 redeploy riêng)
make status / r2-status / health / smoke
```

Biến môi trường & chi tiết redeploy: [CLAUDE.md](CLAUDE.md) · [__document__/deployment.md](__document__/deployment.md).

---

## 8. Tài liệu thêm

- **Hiện trạng 1 trang:** [__document__/STATUS.md](__document__/STATUS.md)
- **Luồng ingest/enrich:** [__document__/ingest_flow.md](__document__/ingest_flow.md)
- **Clustering:** [__document__/clustering.md](__document__/clustering.md)
- **Monitor & alert:** [__document__/monitor.md](__document__/monitor.md)
- **Front-end:** [__document__/frontend.md](__document__/frontend.md) · [__document__/visualize-frontend.md](__document__/visualize-frontend.md)
- **Deploy:** [__document__/deployment.md](__document__/deployment.md)
- **Hướng dẫn cho Claude Code:** [CLAUDE.md](CLAUDE.md)
