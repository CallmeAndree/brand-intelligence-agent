# Runtime 2 — Chat Analyst agent. Dùng khi deploy lên AgentBase (slice sau).
# Ràng buộc AgentBase: listen :8080 + GET /health → 200 (SDK lo sẵn).
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "main.py"]
