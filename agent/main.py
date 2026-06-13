"""Runtime 2 — Chat Analyst agent (AgentBase SDK) + wiring memory tối thiểu.

Entrypoint POST /invocations gọi LLM minimax (VNG MaaS gateway) qua agent_framework,
trả về ChatMessage. Slice add-monitor-workspace bổ sung **memory tối thiểu**:
- Bắt buộc header User-Id/Session-Id khi memory bật (MEMORY_ID set) — KHÔNG fallback default.
- Mỗi turn `create_event` (user + assistant); recall trước khi gọi LLM
  (`search_memory_records` theo namespace actor + list events gần đây) → nhét vào prompt.
- Nhận message `kind="context_inject"` (artifact content_md + cluster_id) → ghi memory event.
- Recall lỗi → degrade an toàn (trả lời không memory), KHÔNG chặn lượt chat.

Local: `python main.py` (port 8080). Đọc BOT_* từ .env. Memory creds
(GREENNODE_CLIENT_ID/SECRET/AGENT_IDENTITY) do runtime AgentBase tự inject.
"""

import asyncio
import os

from agent_framework import Message
from agent_framework_openai import OpenAIChatCompletionClient
from dotenv import load_dotenv
from greennode_agentbase import (
    GreenNodeAgentBaseApp,
    PingStatus,
    RequestContext,
)

try:
    from greennode_agentbase.memory import (
        MemoryClient,
        EventCreateRequest,
        EventPayload,
        MemoryRecordSearchRequest,
    )
except Exception:  # noqa: BLE001 — SDK memory không sẵn → chạy chế độ no-memory
    MemoryClient = None  # type: ignore[assignment]

load_dotenv()

app = GreenNodeAgentBaseApp()

SYSTEM_PROMPT = (
    "Bạn là Brand Intelligence Analyst của VNG, theo dõi và phân tích các mention "
    "tiêu cực về ZaloPay (ZLP) trên mạng xã hội. CHỈ về ZaloPay — không bao gồm Zalo "
    "(app chat là sản phẩm khác). Trả lời bằng tiếng Việt, ngắn gọn, có cấu trúc, "
    "giọng điệu chuyên nghiệp. Nếu chưa đủ dữ liệu để khẳng định, hãy nói rõ thay vì bịa số liệu."
)

MEMORY_ID = os.getenv("MEMORY_ID", "").strip()
MEMORY_STRATEGY_ID = os.getenv("MEMORY_STRATEGY_ID", "default").strip()
RECALL_LIMIT = int(os.getenv("MEMORY_RECALL_LIMIT", "5"))
RECENT_EVENTS = int(os.getenv("MEMORY_RECENT_EVENTS", "6"))


def memory_enabled() -> bool:
    return bool(MEMORY_ID) and MemoryClient is not None


def _build_client() -> OpenAIChatCompletionClient:
    # Chat Analyst = sinh text hội thoại chất lượng → dùng MINIMAX. Cùng gateway
    # (API_KEY/BASE_URL) như Runtime 1.
    return OpenAIChatCompletionClient(
        model=os.environ["MINIMAX_MODEL"],
        api_key=os.environ["API_KEY"],
        base_url=os.environ["BASE_URL"],
    )


def _namespace(user_id: str) -> str:
    return f"/strategies/{MEMORY_STRATEGY_ID}/actors/{user_id}"


async def _create_event(
    client, user_id: str, session_id: str, role: str, message: str, event_type: str = "conversational"
) -> None:
    """Ghi 1 event vào memory (best-effort — lỗi chỉ log, không ném lên)."""
    try:
        await client.create_event_async(
            id=MEMORY_ID,
            actorId=user_id,
            sessionId=session_id,
            request=EventCreateRequest(
                payload=EventPayload(type=event_type, role=role, message=message)
            ),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] create_event lỗi ({event_type}): {exc}")


async def _recall(client, user_id: str, session_id: str, query: str) -> str:
    """Recall ngữ cảnh: semantic records (actor) + event gần đây (session)."""
    parts: list[str] = []
    try:
        records = await client.search_memory_records_async(
            id=MEMORY_ID,
            namespace=_namespace(user_id),
            request=MemoryRecordSearchRequest(query=query, limit=RECALL_LIMIT),
        )
        facts = [
            getattr(r, "memory", None) or (r.get("memory") if isinstance(r, dict) else None)
            for r in (records or [])
        ]
        facts = [f for f in facts if f]
        if facts:
            parts.append("Ghi nhớ liên quan:\n" + "\n".join(f"- {f}" for f in facts))
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] search_memory_records lỗi: {exc}")

    try:
        events = await client.list_events_async(
            id=MEMORY_ID,
            actorId=user_id,
            sessionId=session_id,
            page=1,
            size=RECENT_EVENTS,
        )
        items = getattr(events, "listData", None) or []
        lines = []
        for ev in items:
            payload = getattr(ev, "payload", None)
            role = getattr(payload, "role", None) if payload else None
            msg = getattr(payload, "message", None) if payload else None
            if msg:
                lines.append(f"{role or '?'}: {msg}")
        if lines:
            parts.append("Lịch sử gần đây:\n" + "\n".join(reversed(lines)))
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] list_events lỗi: {exc}")

    return "\n\n".join(parts)


async def _ask(message: str, recall_ctx: str) -> str:
    client = _build_client()
    system = SYSTEM_PROMPT
    if recall_ctx:
        system += "\n\n## Ngữ cảnh từ bộ nhớ (dùng nếu liên quan)\n" + recall_ctx
    response = await client.get_response(
        [Message("system", [system]), Message("user", [message])]
    )
    return str(getattr(response, "text", "") or "")


async def _handle_async(payload: dict, user_id: str, session_id: str) -> dict:
    use_memory = memory_enabled()
    mem = MemoryClient() if use_memory else None

    # --- context_inject: ghi artifact vào memory, không gọi LLM ---
    if (payload or {}).get("kind") == "context_inject":
        content = (payload.get("content_md") or "").strip()
        cluster_id = payload.get("cluster_id")
        if not content:
            return {"role": "assistant", "text": "Không có nội dung artifact để nạp."}
        if mem is not None:
            await _create_event(
                mem,
                user_id,
                session_id,
                role="user",
                message=f"[Ngữ cảnh artifact cụm #{cluster_id}]\n{content}",
                event_type="conversational",
            )
        return {
            "role": "assistant",
            "text": f"Đã nạp ngữ cảnh artifact của cụm #{cluster_id} vào bộ nhớ phiên.",
        }

    message = (payload or {}).get("message", "").strip()
    if not message:
        return {"role": "assistant", "text": "Bạn hãy nhập câu hỏi nhé."}

    recall_ctx = ""
    if mem is not None:
        recall_ctx = await _recall(mem, user_id, session_id, message)
        await _create_event(mem, user_id, session_id, role="user", message=message)

    text = await _ask(message, recall_ctx)

    if text and mem is not None:
        await _create_event(mem, user_id, session_id, role="assistant", message=text)

    if not text:
        return {"role": "assistant", "text": "Xin lỗi, tôi chưa tạo được câu trả lời. Bạn thử lại nhé."}
    return {"role": "assistant", "text": text}


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    """POST /invocations → ChatMessage. Header User-Id/Session-Id bắt buộc khi memory bật."""
    user_id = (getattr(context, "user_id", None) or (payload or {}).get("user_id") or "").strip()
    session_id = (
        getattr(context, "session_id", None) or (payload or {}).get("session_id") or ""
    ).strip()

    # Bắt buộc danh tính khi memory bật — KHÔNG fallback về default-user.
    if memory_enabled() and (not user_id or not session_id):
        missing = []
        if not user_id:
            missing.append("X-GreenNode-AgentBase-User-Id")
        if not session_id:
            missing.append("X-GreenNode-AgentBase-Session-Id")
        return {
            "role": "assistant",
            "text": f"Thiếu header bắt buộc cho memory: {', '.join(missing)}.",
        }

    try:
        return asyncio.run(_handle_async(payload or {}, user_id, session_id))
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] handler error: {exc}")
        return {
            "role": "assistant",
            "text": "Xin lỗi, dịch vụ trả lời đang gặp sự cố. Bạn thử lại sau nhé.",
        }


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(port=port, host="0.0.0.0")
