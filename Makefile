.ONESHELL:
.PHONY: up down rebuild logs help \
        creds cf-tunnel cf-status deploy status endpoint health smoke versions

# ---- Cấu hình (đổi nếu tạo runtime mới / image khác) ----
CONDA     := /home/anhpn8/miniconda3/bin
ROOT      := $(abspath $(CURDIR)/..)
SK        := $(ROOT)/greennode-agentbase-skills/.claude/skills/agentbase/scripts
RID       := runtime-26fc78f5-6f77-4549-8fc4-fd775adcad25
IMAGE     := vcr.vngcloud.vn/111480-abp111664/bi-ingest-enrich
FLAVOR    := runtime-s2-general-2x4
ENVDEPLOY := $(CURDIR)/.env.deploy
ENDPOINT  := https://endpoint-3e5c87ac-ccfd-431c-b020-853e73862c5a.agentbase-runtime.aiplatform.vngcloud.vn
TUNLOG    := /tmp/cf_tunnel.log
TUNPID    := /tmp/cf_tunnel.pid
PATHX     := export PATH="$(CONDA):$$PATH"

help:
	@echo "Local dev:"
	@echo "  make up | down | rebuild | logs"
	@echo "Deploy AgentBase:"
	@echo "  make creds       - tạo lại .greennode.json từ .env (khi lỗi token)"
	@echo "  make cf-tunnel   - bật cloudflared + tự ghi URL vào .env.deploy"
	@echo "  make cf-status   - kiểm tra tunnel còn sống"
	@echo "  make deploy      - build + push + update runtime (redeploy khi code đổi)"
	@echo "  make status      - trạng thái runtime"
	@echo "  make endpoint    - in URL DEFAULT endpoint"
	@echo "  make health      - curl /health endpoint"
	@echo "  make smoke       - POST /ingest/email thử"
	@echo "  make versions    - liệt kê version runtime (để rollback)"

# ---------- Local dev (docker compose trên VM) ----------
up:
	docker compose up -d

down:
	docker compose down

rebuild:
	docker compose up -d --build

logs:
	docker compose logs -f data-backend

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
deploy:
	cd $(ROOT); $(PATHX)
	TAG="v$$(date +%Y%m%d%H%M%S)"; IMG="$(IMAGE):$$TAG"
	echo "==> build $$IMG"
	docker build --platform linux/amd64 -t "$$IMG" $(CURDIR)
	echo "==> login CR + push"
	bash $(SK)/cr.sh credentials docker-login
	docker push "$$IMG"
	echo "==> update runtime $(RID)"
	bash $(SK)/runtime.sh update $(RID) --image "$$IMG" --flavor $(FLAVOR) --env-file $(ENVDEPLOY) --from-cr
	echo "$$IMG" > /tmp/bi_last_image.txt
	echo "==> DONE: $$IMG (chờ ACTIVE: make status)"

status:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh get $(RID) | jq -r '.status'

endpoint:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh endpoints list $(RID) | jq -r '.listData[] | select(.name=="DEFAULT") | .url'

versions:
	cd $(ROOT); $(PATHX)
	bash $(SK)/runtime.sh versions $(RID) | jq -r '.listData[]? | "v\(.version)  \(.imageUrl)"'

health:
	curl -s -o /dev/null -w "%{http_code}\n" $(ENDPOINT)/health

smoke:
	WT=$$(grep -E '^WEBHOOK_TOKEN=' $(ENVDEPLOY) | cut -d= -f2-)
	curl -s -X POST $(ENDPOINT)/ingest/email \
	  -H "X-Webhook-Token: $$WT" -H "Content-Type: application/json" \
	  -d '{"_id":"smoke-001","mention":"ZaloPay test smoke","source":"manual"}' \
	  -w "\nHTTP %{http_code}\n"
