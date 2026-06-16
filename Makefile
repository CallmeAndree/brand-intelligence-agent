.ONESHELL:
.PHONY: up down rebuild logs help agent-logs agent-health \
        creds cf-tunnel cf-status deploy deploy-r1 deploy-r2 status endpoint endpoint-status health smoke versions \
        r2-create r2-endpoint r2-status memory-create \
        stop start frontend frontend-link

# ---- Cấu hình (đổi nếu tạo runtime mới / image khác) ----
CONDA     := /home/anhpn8/miniconda3/bin
ROOT      := $(abspath $(CURDIR)/..)
SK        := $(ROOT)/greennode-agentbase-skills/.claude/skills/agentbase/scripts

# Runtime 1 — ingest + enrich + monitor/alert/generation (FastAPI, root Dockerfile).
# min=max=1 BẮT BUỘC: worker dùng asyncio.Queue in-process, >1 replica phá hàng đợi.
RID       := runtime-26fc78f5-6f77-4549-8fc4-fd775adcad25
IMAGE     := vcr.vngcloud.vn/111480-abp111664/bi-ingest-enrich
FLAVOR    := runtime-s2-general-2x4
ENVDEPLOY := $(CURDIR)/.env.deploy
ENDPOINT  := https://endpoint-3e5c87ac-ccfd-431c-b020-853e73862c5a.agentbase-runtime.aiplatform.vngcloud.vn

# Runtime 2 — Chat Analyst (AgentBase SDK, agent/Dockerfile). Stateless → autoscale.
# RID2/ENDPOINT2 trống cho tới khi chạy 'make r2-create' + 'make r2-endpoint' lần đầu
# → điền giá trị trả về vào 2 dòng dưới (giống cách R1 đã hardcode).
RID2      := runtime-70e6c645-49a7-467d-a3c1-f04955590d4f
IMAGE2    := vcr.vngcloud.vn/111480-abp111664/bi-chat-analyst
FLAVOR2   := runtime-s2-general-2x4
ENVDEPLOY2:= $(CURDIR)/agent/.env.deploy
ENDPOINT2 := https://endpoint-4a0a8967-90e4-4e89-adcb-5d1a3bd94faf.agentbase-runtime.aiplatform.vngcloud.vn
R2_MAXREPLICAS := 3

TUNLOG    := /tmp/cf_tunnel.log
TUNPID    := /tmp/cf_tunnel.pid
PATHX     := export PATH="$(CONDA):$$PATH"
FRONTEND  := $(CURDIR)/frontend
VERCEL    := npx -y vercel@latest

help:
	@echo "Local dev:"
	@echo "  make up | down | rebuild | logs"
	@echo "  make agent-logs   - tail log Runtime 2 (Chat Analyst)"
	@echo "  make agent-health - curl /health agent (host 8092)"
	@echo "Deploy AgentBase:"
	@echo "  make creds       - tạo lại .greennode.json từ .env (khi lỗi token)"
	@echo "  make cf-tunnel   - bật cloudflared + tự ghi URL vào .env.deploy"
	@echo "  make cf-status   - kiểm tra tunnel còn sống"
	@echo "  make deploy      - redeploy CẢ 2 runtime (R1 ingest/enrich + R2 chat)"
	@echo "  make deploy-r1   - chỉ redeploy Runtime 1 (root image, min=max=1)"
	@echo "  make deploy-r2   - chỉ redeploy Runtime 2 (agent/ image, autoscale)"
	@echo "  make status / r2-status - trạng thái Runtime 1 / Runtime 2"
	@echo "  Runtime 2 lần đầu: make memory-create → make r2-create → make r2-endpoint (điền RID2/ENDPOINT2 vào Makefile)"
	@echo "  make endpoint        - in URL DEFAULT endpoint"
	@echo "  make endpoint-status - in status + replica count DEFAULT endpoint"
	@echo "  make stop            - dừng DEFAULT endpoint (halt traffic, KHÔNG xoá)"
	@echo "  make start           - bật lại DEFAULT endpoint sau khi stop"
	@echo "  make health          - curl /health endpoint"
	@echo "  make smoke       - POST /ingest/email thử"
	@echo "  make versions    - liệt kê version runtime (để rollback)"
	@echo "Front-end (Vercel):"
	@echo "  make frontend-link - liên kết thư mục frontend với project Vercel (1 lần, interactive)"
	@echo "  make frontend      - deploy frontend lên Vercel, tự inject DATA_BACKEND_URL tunnel hiện tại"

# ---------- Local dev (docker compose trên VM) ----------
up:
	docker compose up -d

down:
	docker compose down

rebuild:
	docker compose up -d --build

logs:
	docker compose logs -f data-backend

agent-logs:
	docker compose logs -f agent

agent-health:
	curl -s -o /dev/null -w "agent /health: %{http_code}\n" http://localhost:8092/health

# ---------- Credentials ----------
creds:
	cd $(ROOT); $(PATHX)
	CID=$$(grep -E '^IAM_CLIENT_ID=' $(CURDIR)/.env | cut -d= -f2- | tr -d '"')
	SEC=$$(grep -E '^IAM_CLIENT_SECRET=' $(CURDIR)/.env | cut -d= -f2- | tr -d '"')
	printf '%s' "$$SEC" | bash $(SK)/save_iam_credentials.sh --client-id "$$CID" --secret-stdin
	bash $(SK)/check_credentials.sh iam

# ---------- Cloudflare tunnel (data-backend) ----------
cf-tunnel:
	curl -s -o /dev/null -w "data-backend health: %{http_code}\n" http://localhost:8091/health
	nohup cloudflared tunnel --url http://localhost:8091 --no-autoupdate > $(TUNLOG) 2>&1 & echo $$! > $(TUNPID)
	sleep 8
	URL=$$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' $(TUNLOG) | head -1)
	echo "tunnel URL: $$URL"
	if [ -n "$$URL" ]; then \
	  sed -i "s|^DATA_BACKEND_URL=.*|DATA_BACKEND_URL=$$URL|" $(ENVDEPLOY); \
	  echo "==> đã cập nhật DATA_BACKEND_URL trong .env.deploy (nhớ 'make deploy' để runtime nạp URL mới)"; \
	else \
	  echo "LỖI: chưa lấy được URL — xem $(TUNLOG)"; \
	fi

cf-status:
	if ps -p $$(cat $(TUNPID) 2>/dev/null) >/dev/null 2>&1; then echo "tunnel UP (pid $$(cat $(TUNPID)))"; else echo "tunnel DEAD"; fi
	URL=$$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' $(TUNLOG) 2>/dev/null | head -1)
	echo "URL: $$URL"
	[ -n "$$URL" ] && curl -s -o /dev/null -w "tunnel /health: %{http_code}\n" "$$URL/health" || true

# ---------- Deploy / redeploy ----------
# 'make deploy' = redeploy CẢ 2 runtime. Khi chỉ đổi 1 bên → 'make deploy-r1' hoặc
# 'make deploy-r2' (khỏi build+push thừa runtime kia).
deploy: deploy-r1 deploy-r2

# Runtime 1 — build root image (app + data_backend + scripts), ép min=max=1 (queue in-process).
deploy-r1:
	cd $(ROOT); $(PATHX)
	TAG="v$$(date +%Y%m%d%H%M%S)"; IMG="$(IMAGE):$$TAG"
	echo "==> [R1] build $$IMG"
	docker build --platform linux/amd64 -t "$$IMG" $(CURDIR)
	echo "==> login CR + push"
	bash $(SK)/cr.sh credentials docker-login
	docker push "$$IMG"
	echo "==> [R1] update runtime $(RID) (min=max=1)"
	bash $(SK)/runtime.sh update $(RID) --image "$$IMG" --flavor $(FLAVOR) --env-file $(ENVDEPLOY) --from-cr \
	  --min-replicas 1 --max-replicas 1
	echo "$$IMG" > /tmp/bi_last_image.txt
	echo "==> [R1] DONE: $$IMG (chờ ACTIVE: make status)"

# Runtime 2 — build agent image (Chat Analyst SDK), autoscale 1..$(R2_MAXREPLICAS) (stateless).
deploy-r2:
	cd $(ROOT); $(PATHX)
	if [ -z "$(RID2)" ]; then echo "LỖI: RID2 trống — chạy 'make r2-create' lần đầu rồi điền RID2 vào Makefile"; exit 1; fi
	TAG="v$$(date +%Y%m%d%H%M%S)"; IMG="$(IMAGE2):$$TAG"
	echo "==> [R2] build $$IMG (agent/)"
	docker build --platform linux/amd64 -t "$$IMG" $(CURDIR)/agent
	echo "==> login CR + push"
	bash $(SK)/cr.sh credentials docker-login
	docker push "$$IMG"
	echo "==> [R2] update runtime $(RID2) (min=1 max=$(R2_MAXREPLICAS))"
	bash $(SK)/runtime.sh update $(RID2) --image "$$IMG" --flavor $(FLAVOR2) --env-file $(ENVDEPLOY2) --from-cr \
	  --min-replicas 1 --max-replicas $(R2_MAXREPLICAS)
	echo "$$IMG" > /tmp/bi_last_image_r2.txt
	echo "==> [R2] DONE: $$IMG (chờ ACTIVE: make r2-status)"

# ---------- Runtime 2: tạo lần đầu (one-time) ----------
# Quy trình: 1) tạo memory store: make memory-create → điền MEMORY_ID vào agent/.env.deploy
#            2) make r2-create  → build+push agent image + tạo runtime → điền RID2 vào Makefile
#            3) make r2-endpoint→ tạo endpoint DEFAULT + in URL → điền ENDPOINT2 vào Makefile
#            4) make deploy (hoặc make frontend) như bình thường.
r2-create:
	cd $(ROOT); $(PATHX)
	if [ ! -f "$(ENVDEPLOY2)" ]; then echo "LỖI: thiếu $(ENVDEPLOY2) — copy từ agent/.env.deploy.example rồi điền API_KEY/BASE_URL/MINIMAX_MODEL/MEMORY_ID"; exit 1; fi
	TAG="v$$(date +%Y%m%d%H%M%S)"; IMG="$(IMAGE2):$$TAG"
	echo "==> [R2] build+push $$IMG (agent/)"
	docker build --platform linux/amd64 -t "$$IMG" $(CURDIR)/agent
	bash $(SK)/cr.sh credentials docker-login
	docker push "$$IMG"
	echo "==> [R2] create runtime bi-chat-analyst (min=1 max=$(R2_MAXREPLICAS))"
	bash $(SK)/runtime.sh create --name bi-chat-analyst --description "Chat Analyst (Runtime 2)" \
	  --image "$$IMG" --flavor $(FLAVOR2) --env-file $(ENVDEPLOY2) --from-cr \
	  --min-replicas 1 --max-replicas $(R2_MAXREPLICAS) | tee /tmp/bi_r2_create.json
	echo "==> Lấy RID2 từ JSON trên (field .id) rồi điền vào dòng 'RID2 :=' trong Makefile, sau đó: make r2-endpoint"

r2-endpoint:
	cd $(ROOT); $(PATHX)
	if [ -z "$(RID2)" ]; then echo "LỖI: RID2 trống — điền RID2 (từ make r2-create) vào Makefile trước"; exit 1; fi
	echo "==> [R2] tạo endpoint DEFAULT cho $(RID2)"
	bash $(SK)/runtime.sh endpoints create $(RID2) --name DEFAULT || true
	echo "==> [R2] URL endpoint (điền vào 'ENDPOINT2 :=' trong Makefile + dùng cho AGENT_BASE_URL):"
	bash $(SK)/runtime.sh endpoints list $(RID2) | jq -r '.listData[] | select(.name=="DEFAULT") | .url'

r2-status:
	cd $(ROOT); $(PATHX)
	if [ -z "$(RID2)" ]; then echo "LỖI: RID2 trống"; exit 1; fi
	bash $(SK)/runtime.sh get $(RID2) | jq -r '.status'

# Tạo memory store cho Runtime 2 (one-time). In .id → điền MEMORY_ID vào agent/.env.deploy.
# namespaceTemplate PHẢI khớp cách agent build namespace: /strategies/{memoryStrategyId}/actors/{actorId}
# (agent/main.py dùng MEMORY_STRATEGY_ID + user_id). namespaceTemplate + auto-generate là BẮT BUỘC (thiếu → HTTP 400).
memory-create:
	cd $(ROOT); $(PATHX)
	bash $(SK)/memory.sh create --name bi-chat-memory --description "Chat Analyst conversational memory" \
	  --expiry-days 30 --strategy-name semantic-facts --strategy-type SEMANTIC \
	  --namespace-template "/strategies/{memoryStrategyId}/actors/{actorId}" --auto-generate | tee /tmp/bi_memory_create.json
	echo "==> Điền vào $(ENVDEPLOY2):  MEMORY_ID = .id  ;  MEMORY_STRATEGY_ID = .longTermMemoryStrategies[0].id"

status:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh get $(RID) | jq -r '.status'

endpoint:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh endpoints list $(RID) | jq -r '.listData[] | select(.name=="DEFAULT") | .url'

endpoint-status:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh endpoints list $(RID) | jq -r '.listData[] | select(.name=="DEFAULT") | "\(.name)  status=\(.status)  replicas=\(.currentReplicaCount)"'

# ---------- Lifecycle endpoint (stop/start — KHÔNG xoá runtime) ----------
# Worker enrich dùng asyncio.Queue in-process: stop = kill container, mọi record
# đang enrich dở mất khỏi queue nhưng vẫn còn status=pending trong Mongo → start
# lại worker tự quét pending chạy tiếp (không mất dữ liệu, chỉ trễ).
stop:
	cd $(ROOT); $(PATHX)
	EID=$$(bash $(SK)/runtime.sh endpoints list $(RID) | jq -r '.listData[] | select(.name=="DEFAULT") | .id')
	if [ -z "$$EID" ] || [ "$$EID" = "null" ]; then echo "LỖI: không tìm thấy DEFAULT endpoint"; exit 1; fi
	echo "==> stop endpoint $$EID (runtime $(RID))"
	bash $(SK)/runtime.sh endpoints stop $(RID) $$EID
	echo "==> đã gửi stop — poll trạng thái bằng: make endpoint-status"

start:
	cd $(ROOT); $(PATHX)
	EID=$$(bash $(SK)/runtime.sh endpoints list $(RID) | jq -r '.listData[] | select(.name=="DEFAULT") | .id')
	if [ -z "$$EID" ] || [ "$$EID" = "null" ]; then echo "LỖI: không tìm thấy DEFAULT endpoint"; exit 1; fi
	echo "==> start endpoint $$EID (runtime $(RID))"
	bash $(SK)/runtime.sh endpoints start $(RID) $$EID
	echo "==> đã gửi start — poll trạng thái bằng: make endpoint-status"

versions:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh versions $(RID) | jq -r '.listData[]? | "v\(.version)  \(.imageUrl)"'

health:
	curl -s -o /dev/null -w "%{http_code}\n" $(ENDPOINT)/health

# ---------- Debug logs / events (chẩn đoán runtime ERROR) ----------
r1-logs:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh logs $(RID) --limit 60 --order desc

# Lọc marker boot/lỗi (loại bỏ spam /health) — chẩn đoán replica mới fail rollout.
r1-boot:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh logs $(RID) --limit 300 --order desc | grep '"content"' | grep -ivE 'GET /health' | head -40

r2-boot:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh logs $(RID2) --limit 300 --order desc | grep '"content"' | grep -ivE 'GET /health' | head -40

r2-logs:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh logs $(RID2) --limit 60 --order desc

r1-detail:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh get $(RID)

r2-detail:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh get $(RID2) | jq '{status, statusReason, updatedAt, image: .imageUrl, flavor: .flavorName, min: .minReplicas, max: .maxReplicas, net: .networkMode}'

rt-list:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh list | jq -r '.listData[]? | "\(.status)\t\(.name)\t\(.id)"'

flavors:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh flavors

r1-ep:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh endpoints list $(RID) | jq '.listData[] | select(.name=="DEFAULT")'

r1-events:
	cd $(ROOT); $(PATHX)
	EID=$$(bash $(SK)/runtime.sh endpoints list $(RID) | jq -r '.listData[] | select(.name=="DEFAULT") | .id')
	bash $(SK)/runtime.sh endpoints events $(RID) $$EID

r2-events:
	cd $(ROOT); $(PATHX)
	EID=$$(bash $(SK)/runtime.sh endpoints list $(RID2) | jq -r '.listData[] | select(.name=="DEFAULT") | .id')
	bash $(SK)/runtime.sh endpoints events $(RID2) $$EID

smoke:
	WT=$$(grep -E '^WEBHOOK_TOKEN=' $(ENVDEPLOY) | cut -d= -f2-)
	curl -s -X POST $(ENDPOINT)/ingest/email \
	  -H "X-Webhook-Token: $$WT" -H "Content-Type: application/json" \
	  -d '{"_id":"smoke-001","mention":"Zalopay test smoke","source":"manual"}' \
	  -w "\nHTTP %{http_code}\n"

# ---------- Front-end (Vercel) ----------
# Front-end Vercel KHÔNG nối Mongo trực tiếp (Mongo private trên VM). Nó đọc DB qua
# data-backend HTTP facade qua Cloudflare quick tunnel — GIỐNG Runtime 1 (REPO_MODE=http).
# Nguồn URL tunnel + token là DUY NHẤT từ .env.deploy (cùng giá trị 'make cf-tunnel' ghi).
#
# Lần đầu: 'make frontend-link' (interactive) để liên kết project. Sau đó mỗi lần tunnel
# đổi URL → chỉ cần 'make frontend' (tự push env mới + redeploy prod).
# Headless/CI: set VERCEL_TOKEN trong môi trường trước khi gọi.
frontend-link:
	cd $(FRONTEND)
	$(VERCEL) link

frontend:
	cd $(FRONTEND)
	URL=$$(grep -E '^DATA_BACKEND_URL=' $(ENVDEPLOY) | cut -d= -f2- | tr -d '"')
	TOK=$$(grep -E '^DATA_BACKEND_TOKEN=' $(ENVDEPLOY) | cut -d= -f2- | tr -d '"')
	if [ -z "$$URL" ]; then echo "LỖI: DATA_BACKEND_URL trống trong .env.deploy — chạy 'make cf-tunnel' trước"; exit 1; fi
	TKF=""; [ -n "$$VERCEL_TOKEN" ] && TKF="--token $$VERCEL_TOKEN"
	set_env() { $(VERCEL) env rm "$$1" production -y $$TKF >/dev/null 2>&1 || true; printf '%s' "$$2" | $(VERCEL) env add "$$1" production $$TKF >/dev/null; echo "   set $$1"; }
	echo "==> đẩy env Vercel (production), tunnel hiện tại: $$URL"
	set_env DATA_BACKEND_URL "$$URL"
	set_env DATA_BACKEND_TOKEN "$$TOK"
	if [ -n "$(ENDPOINT2)" ]; then set_env AGENT_BASE_URL "$(ENDPOINT2)"; else echo "   (bỏ qua AGENT_BASE_URL: ENDPOINT2 trống — chạy 'make r2-endpoint' + điền ENDPOINT2 vào Makefile để chat dùng Runtime 2)"; fi
	if [ -n "$(ENDPOINT)" ]; then \
	  set_env RUNTIME1_BASE_URL "$(ENDPOINT)"; \
	  R1TOK=$$(grep -E '^RUNTIME1_API_TOKEN=' $(ENVDEPLOY) | cut -d= -f2- | tr -d '"'); \
	  [ -z "$$R1TOK" ] && R1TOK=$$(grep -E '^RUNTIME1_API_TOKEN=' $(CURDIR)/.env | cut -d= -f2- | tr -d '"'); \
	  set_env RUNTIME1_API_TOKEN "$$R1TOK"; \
	else echo "   (bỏ qua RUNTIME1_BASE_URL: ENDPOINT trống — generation/alert sẽ 503)"; fi
	echo "==> deploy prod"
	$(VERCEL) --prod --yes $$TKF
	@echo "(AGENT_BASE_URL = endpoint Runtime 2 = $(ENDPOINT2); KHÁC API_KEY/BASE_URL LLM gateway trong .env.deploy)"
