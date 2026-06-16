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

import json
import os
import re
from datetime import datetime, timezone

import httpx
from agent_framework import Message
from agent_framework_openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

from text_gen import complete_text, stream_text
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
    "Bạn là Zalopay 505 Analyst của VNG, theo dõi và phân tích các mention "
    "tiêu cực về Zalopay (ZLP) trên mạng xã hội. CHỈ về Zalopay — không bao gồm Zalo "
    "(app chat là sản phẩm khác). Trả lời bằng tiếng Việt, ngắn gọn, có cấu trúc, "
    "giọng điệu chuyên nghiệp. Nếu chưa đủ dữ liệu để khẳng định, hãy nói rõ thay vì bịa số liệu."
)

MEMORY_ID = os.getenv("MEMORY_ID", "").strip()
MEMORY_STRATEGY_ID = os.getenv("MEMORY_STRATEGY_ID", "default").strip()
RECALL_LIMIT = int(os.getenv("MEMORY_RECALL_LIMIT", "5"))
# Working memory: số message (user/assistant) gần nhất dựng lại thành lượt hội thoại
# gửi vào LLM. 20 ≈ 10 lượt hỏi-đáp — đủ để agent nhớ mạch hội thoại gần (không "quên
# lượt vừa nói"); recall semantic lo fact cũ hơn. Tăng nữa nếu cần, đánh đổi token prompt.
MEMORY_TURN_WINDOW = int(os.getenv("MEMORY_TURN_WINDOW", "20"))
# Cắt 1 message quá dài trước khi nhét vào prompt history (tránh 1 artifact dài nuốt cửa sổ).
MESSAGE_MAX_CHARS = int(os.getenv("MEMORY_MESSAGE_MAX_CHARS", "4000"))

# Runtime 1 — RT2 gọi để sinh nội dung (/generate), truy data (/query/*) và lấy persona
# (/prompts/chat-system). RT2 KHÔNG import app/ → mọi tác vụ này đi qua HTTP + token.
RUNTIME1_BASE_URL = os.getenv("RUNTIME1_BASE_URL", "").strip().rstrip("/")
RUNTIME1_API_TOKEN = os.getenv("RUNTIME1_API_TOKEN", "").strip()
RUNTIME1_TIMEOUT = float(os.getenv("RUNTIME1_TIMEOUT", "120"))

# Persona analyst lấy từ RT1 GET /prompts/chat-system (cache 1 lần). Fallback hằng số.
_PERSONA_CACHE: dict[str, str] = {}

# Playbook explain (giải thích data point dashboard) lấy từ RT1 /prompts/chat-explain (cache).
_EXPLAIN_CACHE: dict[str, str] = {}
_EXPLAIN_FALLBACK = (
    "Bạn đang giải thích một data point trên dashboard mention tiêu cực về Zalopay (ZLP). "
    "Câu hỏi đã nhúng sẵn số liệu quan sát trên biểu đồ — bám đúng số đó, không nói lệch, "
    "không bịa. Hệ thống đã truy sẵn dữ liệu THẬT (mẫu mention/chi tiết cụm) trong phần 'Dữ "
    "liệu đã truy được' — BẮT BUỘC trích 2–4 mention thật để chống lưng, KHÔNG nói nguyên "
    "nhân chung chung khi không có dẫn chứng. Phần dữ liệu rỗng → nói thẳng chưa đủ dữ liệu "
    "để kết luận, không bịa. TUYỆT ĐỐI không tự gọi công cụ, không in cú pháp gọi hàm. CHỈ "
    "về Zalopay, tiếng Việt, gọn."
)


def runtime1_configured() -> bool:
    return bool(RUNTIME1_BASE_URL)


def memory_enabled() -> bool:
    return bool(MEMORY_ID) and MemoryClient is not None


def _list_data(resp) -> list:
    """Lấy mảng item từ ListResponse* của Memory SDK.

    Pydantic field là `list_data` (snake_case) — đọc `listData` luôn ra None
    (đây chính là bug khiến recall event gần đây + lịch sử phiên rỗng). Fallback
    cả 2 tên + key dict cho chắc.
    """
    if resp is None:
        return []
    return (
        getattr(resp, "list_data", None)
        or getattr(resp, "listData", None)
        or (resp.get("list_data") if isinstance(resp, dict) else None)
        or []
    )


def _event_ts(item) -> str | None:
    """Đọc event_timestamp từ event SDK (object) hoặc dict."""
    return getattr(item, "event_timestamp", None) or (
        item.get("event_timestamp") if isinstance(item, dict) else None
    )


def _sort_events_asc(items: list) -> list:
    """Sort event tăng dần theo `event_timestamp`.

    Item thiếu ts dồn về cuối nhưng GIỮ thứ tự gốc (stable sort) — không đảo lộn
    các event có timestamp, không vỡ khi thiếu ts (D2).
    """
    return sorted(items, key=lambda it: (_event_ts(it) is None, _event_ts(it) or ""))


def _build_client() -> OpenAIChatCompletionClient:
    # Chat Analyst = sinh text hội thoại chất lượng → dùng MINIMAX. Cùng gateway
    # (API_KEY/BASE_URL) như Runtime 1.
    return OpenAIChatCompletionClient(
        model=os.environ["MINIMAX_MODEL"],
        api_key=os.environ["API_KEY"],
        base_url=os.environ["BASE_URL"],
    )


async def _rt1_post(path: str, body: dict) -> dict:
    """POST sang Runtime 1 (kèm X-Runtime1-Token). Trả JSON dict; raise nếu lỗi HTTP."""
    async with httpx.AsyncClient(timeout=RUNTIME1_TIMEOUT) as client:
        resp = await client.post(
            f"{RUNTIME1_BASE_URL}{path}",
            json=body,
            headers={"X-Runtime1-Token": RUNTIME1_API_TOKEN},
        )
        resp.raise_for_status()
        return resp.json()


async def _rt1_post_stream(path: str, body: dict):
    """Stream SSE từ Runtime 1 (vd /generate/stream) → yield từng delta text.

    Parse SSE theo cặp dòng `event:`/`data:` (dòng trống reset event). Chỉ quan tâm
    `delta` (lấy .text) và `error` (raise để caller xử lý fallback). Raise nếu HTTP lỗi.
    """
    async with httpx.AsyncClient(timeout=RUNTIME1_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{RUNTIME1_BASE_URL}{path}",
            json=body,
            headers={"X-Runtime1-Token": RUNTIME1_API_TOKEN},
        ) as resp:
            resp.raise_for_status()
            event: str | None = None
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line[len("data:"):].strip())
                    except Exception:  # noqa: BLE001 — bỏ qua data hỏng, stream tiếp
                        continue
                    if event == "delta":
                        text = data.get("text") or ""
                        if text:
                            yield text
                    elif event == "error":
                        raise RuntimeError(data.get("message") or "RT1 stream error")
                elif line == "":
                    event = None


async def _get_persona() -> str:
    """Persona analyst: lấy 1 lần từ RT1 /prompts/chat-system, cache; fallback hằng số."""
    if "persona" in _PERSONA_CACHE:
        return _PERSONA_CACHE["persona"]
    persona = SYSTEM_PROMPT
    if runtime1_configured():
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{RUNTIME1_BASE_URL}/prompts/chat-system")
                resp.raise_for_status()
                persona = (resp.json().get("prompt") or "").strip() or SYSTEM_PROMPT
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] lấy persona RT1 lỗi (fallback hằng số): {exc}")
    _PERSONA_CACHE["persona"] = persona
    return persona


async def _get_explain_playbook() -> str:
    """Playbook explain: lấy 1 lần từ RT1 /prompts/chat-explain, cache; fallback hằng số."""
    if "explain" in _EXPLAIN_CACHE:
        return _EXPLAIN_CACHE["explain"]
    text = _EXPLAIN_FALLBACK
    if runtime1_configured():
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{RUNTIME1_BASE_URL}/prompts/chat-explain")
                resp.raise_for_status()
                text = (resp.json().get("prompt") or "").strip() or _EXPLAIN_FALLBACK
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] lấy playbook explain RT1 lỗi (fallback hằng số): {exc}")
    _EXPLAIN_CACHE["explain"] = text
    return text


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


async def _recall_facts(client, user_id: str, query: str) -> str:
    """Recall fact dài hạn (semantic records, namespace actor) → text cho system prompt.

    RIÊNG với working memory turns (D1): phần này là "ghi nhớ" trừu tượng đã chắt lọc,
    KHÔNG phải lượt hội thoại — nhét vào system như tham khảo, không làm mạch chỉ định.
    """
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
            return "Ghi nhớ liên quan:\n" + "\n".join(f"- {f}" for f in facts)
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] search_memory_records lỗi: {exc}")
    return ""


async def _history_turns(client, user_id: str, session_id: str) -> list[Message]:
    """Working memory (D1): list_events sort tăng → N message gần nhất → list[Message].

    Map role event → role chat (user/assistant), cắt message quá dài. Đặt GIỮA system
    và message hiện tại → LLM coi là hội thoại thật, giữ được mạch chỉ định ("Hay hơn").
    """
    try:
        events = await client.list_events_async(
            id=MEMORY_ID,
            actorId=user_id,
            sessionId=session_id,
            page=1,
            size=max(MEMORY_TURN_WINDOW * 3, 30),
        )
        items = _sort_events_asc(_list_data(events))
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] list_events (history) lỗi: {exc}")
        return []

    turns: list[Message] = []
    for ev in items:
        payload = getattr(ev, "payload", None)
        role = getattr(payload, "role", None) if payload else None
        msg = getattr(payload, "message", None) if payload else None
        if not msg:
            continue
        chat_role = "user" if role == "user" else "assistant"
        turns.append(Message(chat_role, [msg[:MESSAGE_MAX_CHARS]]))
    return turns[-MEMORY_TURN_WINDOW:]


async def _history_text(client, user_id: str, session_id: str) -> str:
    """Ngữ cảnh phiên dạng text (cho skill /generate): các lượt gần nhất + artifact đã inject.

    Skill chạy ở RT1 cần ngữ cảnh tự do → gói các lượt hội thoại gần nhất thành text.
    Artifact "Gửi sang Chat" đã ghi memory role=user (prefix [Ngữ cảnh artifact...]) → có ở đây.
    """
    if client is None:
        return ""
    turns = await _history_turns(client, user_id, session_id)
    lines: list[str] = []
    for m in turns:
        who = "Người dùng" if str(m.role) == "user" else "Analyst"
        lines.append(f"{who}: {m.text}")
    return "\n".join(lines)


# ---- Tool catalog + điều phối (D3/D4) ----
# Enum mirror enrichment/domain/models.py (RT2 không import app/ → liệt kê tay để
# GỢI Ý cho LLM; RT1 vẫn validate cứng + 422 nếu sai → đây chỉ là guidance).
_PRODUCT_AREAS = [
    "Transfer", "Bill", "OTA", "Telco", "Binding",
    "Financial Service", "Loyalty", "Daily Life Service", "Entertainment",
]
_INTENTS = [
    "khiếu nại/phàn nàn", "hỏi/cần hỗ trợ", "cảnh báo/tố cáo", "mỉa mai/châm biếm",
    "so sánh đối thủ", "góp ý/đề xuất", "spam/cảm thán/vô nghĩa",
]

# Trần số vòng gọi tool mỗi lượt: đủ cho explain (trend + mentions + 1 dự phòng) mà
# không kéo dài độ trễ. Router được hỏi lại sau MỖI tool (có kèm dữ liệu đã truy) để
# quyết định gọi tiếp hay trả lời → "truy vấn RỒI trả lời", không "truy vấn rồi dừng".
MAX_TOOL_ROUNDS = 3

# Nhãn tool thân thiện cho chip trạng thái "🔍 Đang truy dữ liệu: …" hiển thị ở FE.
_TOOL_LABELS = {
    "get_mentions": "danh sách mention",
    "get_trend": "xu hướng theo thời gian",
    "get_cluster_detail": "chi tiết cụm",
    "compare_periods": "so sánh giữa các kỳ",
    "search_mentions": "tìm mention liên quan",
}


def _tool_guide(today: str) -> str:
    return f"""Bạn là BỘ ĐIỀU PHỐI cho một analyst thương hiệu Zalopay. Dựa trên câu hỏi của người dùng (và lịch sử hội thoại), hãy quyết định MỘT hành động và trả về DUY NHẤT một object JSON (không giải thích, không markdown).

Hôm nay là {today}. Khoảng ngày dùng định dạng "YYYY-MM-DD".

Các hành động:
1. Trả lời trực tiếp (không cần dữ liệu): {{"action":"answer"}}
2. Truy dữ liệu bằng MỘT tool: {{"action":"tool","tool":<tên>,"params":{{...}}}}
3. Sinh nội dung bằng MỘT skill: {{"action":"skill","skill_type":<loại>,"cluster_id":<int hoặc bỏ trống>}}

TOOL (chỉ chọn khi cần SỐ LIỆU/DANH SÁCH mention thật):
- get_mentions params: from,to (bắt buộc), platform?, severity_min?/severity_max?(1-10), product_area?(enum), intent?(enum), actionable?(bool), cluster_id?, text_contains?, limit(≤50)
- get_trend params: metric(volume|avg_severity|critical_count), window(day|week|month), from, to, group_by?(platform|product_area)
- get_cluster_detail params: cluster_id(int)
- compare_periods params: metric(volume|avg_severity|critical_count), period_a{{from,to}}, period_b{{from,to}}
- search_mentions params: query(str), limit(≤20)

enum product_area: {", ".join(_PRODUCT_AREAS)}
enum intent: {", ".join(_INTENTS)}

SKILL (chỉ chọn khi người dùng yêu cầu VIẾT/SOẠN nội dung):
- content: viết bài/nội dung truyền thông
- design_brief: brief thiết kế
- response_plan: kế hoạch ứng phó

Nếu câu hỏi chỉ là chào hỏi/giải thích/khái niệm → action "answer". Chỉ trả JSON."""


def _extract_json(text: str) -> dict | None:
    """Trích object JSON đầu tiên từ output LLM (đã strip think). None nếu không có."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        return None


async def _route_decision(
    llm, history_turns: list, message: str, tool_contexts: list[str] | None = None
) -> dict:
    """Gọi LLM (structured-output) chọn answer|tool|skill. Lỗi/parse fail → answer.

    `tool_contexts` = dữ liệu đã truy ở các vòng trước (loop). Khi có, router được nhắc:
    đủ để trả lời → "answer"; cần thêm số liệu khác → chọn tool tiếp (params KHÁC, không lặp).
    """
    today = datetime.now(timezone.utc).date().isoformat()
    msgs = [Message("system", [_tool_guide(today)]), *history_turns, Message("user", [message])]
    if tool_contexts:
        msgs.append(
            Message(
                "user",
                [
                    "## Dữ liệu ĐÃ truy được ở các bước trước:\n"
                    + "\n\n".join(tool_contexts)
                    + "\n\nNếu đã ĐỦ để trả lời người dùng → {\"action\":\"answer\"}. "
                    "Nếu cần THÊM số liệu/danh sách khác (vd mẫu mention cụ thể cho slice này) "
                    "→ chọn tool tiếp theo với params KHÁC. TUYỆT ĐỐI không lặp lại tool+params y hệt."
                ],
            )
        )
    try:
        raw = await complete_text(llm, msgs, max_tokens=600, temperature=0.0)
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] route_decision lỗi: {exc}")
        return {"action": "answer"}
    decision = _extract_json(raw) or {"action": "answer"}
    if decision.get("action") not in {"answer", "tool", "skill"}:
        decision = {"action": "answer"}
    return decision


def _format_chart_points(charts: list) -> str:
    """Trải data point của chart (get_trend/compare_periods) thành text cho LLM.

    rows rỗng với 2 tool chuỗi thời gian → số liệu CHỈ nằm trong charts.series; nếu
    không trải ra, LLM "mù" (chỉ thấy total) → diễn giải xu hướng nghèo nàn. Ghép
    trục x với từng series để LLM thấy đỉnh/đáy/biến thiên."""
    lines: list[str] = []
    for ch in charts:
        xaxis = ch.get("xAxis") or []
        for s in ch.get("series") or []:
            name = s.get("name") or "giá trị"
            pts = ", ".join(
                f"{xaxis[i] if i < len(xaxis) else i}={v}"
                for i, v in enumerate(s.get("data") or [])
            )
            lines.append(f"- {name}: {pts}")
    return "\n".join(lines)


def _format_tool_result(tool: str, data: dict) -> str:
    """Gói ToolResult (rows/summary/charts) thành text gọn cho LLM diễn giải. Cắt rows dài."""
    summary = data.get("summary") or {}
    rows = data.get("rows") or []
    charts = data.get("charts") or []
    parts = [f"Tool: {tool}"]
    if summary:
        parts.append("Tóm tắt: " + json.dumps(summary, ensure_ascii=False)[:1500])
    if charts:
        points = _format_chart_points(charts)
        if points:
            parts.append("Số liệu theo trục thời gian/kỳ:\n" + points[:2000])
    if rows:
        trimmed = []
        for r in rows[:12]:
            d = {k: v for k, v in r.items() if k != "summary_embedding"}
            trimmed.append(d)
        parts.append("Dữ liệu (tối đa 12 dòng): " + json.dumps(trimmed, ensure_ascii=False)[:4000])
    if not summary and not rows and not charts:
        parts.append("(không có kết quả)")
    return "\n".join(parts)


def _explain_tool(eq: dict) -> tuple[str | None, dict]:
    """Chọn tool + params TẤT ĐỊNH cho prefetch explain từ `explain_query` (FE suy ra).

    Có `cluster_id` → `get_cluster_detail` (chi tiết cụm + mention thành viên). Ngược lại
    → `get_mentions` đúng lát cắt (from/to bắt buộc + product_area/platform/text_contains
    nếu có). Thiếu cả cluster_id lẫn from/to → (None, {}) → không prefetch (degrade an toàn).
    """
    cid = eq.get("cluster_id")
    if cid is not None:
        try:
            return "get_cluster_detail", {"cluster_id": int(cid)}
        except (TypeError, ValueError):
            pass
    frm, to = eq.get("from"), eq.get("to")
    if not (frm and to):
        return None, {}
    params: dict = {"from": frm, "to": to, "limit": 30}
    for k in ("product_area", "platform", "text_contains"):
        v = eq.get(k)
        if v:
            params[k] = v
    # keyword_group_id có thể là 0/-1 (nhóm hợp lệ) → check is not None, không dùng truthy.
    kgid = eq.get("keyword_group_id")
    if kgid is not None:
        params["keyword_group_id"] = kgid
    return "get_mentions", params


async def _context_inject(mem, user_id: str, session_id: str, payload: dict) -> dict:
    """Ghi artifact (content_md + cluster_id) vào memory, không gọi LLM. Trả ChatMessage.

    D9: nếu payload mang `skill_type` thuộc 5 skill Monitor → marker GẮN danh tính skill
    (`[Ngữ cảnh: nội dung "<nhãn>" của cụm #N — có thể chỉnh theo yêu cầu]`) để recall/
    loadSession + history thể hiện linkage kể cả khi mỏ neo client (D7) không còn. Thiếu
    `skill_type` → giữ marker cũ (`[Ngữ cảnh artifact cụm #N]`) tương thích ngược.
    """
    content = (payload.get("content_md") or "").strip()
    cluster_id = payload.get("cluster_id")
    skill_type = (payload.get("skill_type") or "").strip()
    if not content:
        return {"role": "assistant", "text": "Không có nội dung artifact để nạp."}
    if skill_type in _SKILL_LABELS:
        marker = (
            f'[Ngữ cảnh: nội dung "{_SKILL_LABELS[skill_type]}" của cụm #{cluster_id} '
            "— có thể chỉnh theo yêu cầu]"
        )
    else:
        marker = f"[Ngữ cảnh artifact cụm #{cluster_id}]"
    if mem is not None:
        await _create_event(
            mem,
            user_id,
            session_id,
            role="user",
            message=f"{marker}\n{content}",
            event_type="conversational",
        )
    return {
        "role": "assistant",
        "text": f"Đã nạp ngữ cảnh artifact của cụm #{cluster_id} vào bộ nhớ phiên.",
    }


async def _list_sessions(mem, user_id: str) -> dict:
    """Liệt kê các phiên của actor + preview (event đầu tiên gần nhất)."""
    if mem is None:
        return {"sessions": []}
    sessions: list[dict] = []
    try:
        resp = await mem.list_sessions_async(id=MEMORY_ID, actorId=user_id, page=1, size=30)
        items = _list_data(resp)
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] list_sessions lỗi: {exc}")
        return {"sessions": []}

    for s in items[:20]:
        sid = getattr(s, "session_id", None) or getattr(s, "sessionId", None)
        if not sid:
            continue
        preview, updated_at = "", None
        try:
            evs = await mem.list_events_async(
                id=MEMORY_ID, actorId=user_id, sessionId=sid, page=1, size=20
            )
            ev_items = _sort_events_asc(_list_data(evs))  # tăng dần → event mới nhất ở cuối
            # Preview = message MỚI NHẤT của phiên; updated_at = ts của nó.
            for ev in reversed(ev_items):
                payload = getattr(ev, "payload", None)
                msg = getattr(payload, "message", None) if payload else None
                if msg:
                    preview = msg[:80]
                    updated_at = _event_ts(ev)
                    break
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] list_sessions preview lỗi ({sid}): {exc}")
        # Bỏ qua phiên "ma": Memory API không có endpoint xóa cấp session nên
        # `_delete_session` chỉ xóa từng event → session metadata vẫn còn nhưng rỗng.
        # Không message nào (updated_at None) ⇒ coi như đã xóa, không hiển thị lại.
        if updated_at is None and not preview:
            continue
        sessions.append({"session_id": sid, "updated_at": updated_at, "preview": preview})
    return {"sessions": sessions}


async def _list_events(mem, user_id: str, session_id: str) -> dict:
    """Liệt kê event của 1 phiên → [{role, text, ts}] theo thứ tự thời gian."""
    if mem is None or not session_id:
        return {"events": []}
    try:
        resp = await mem.list_events_async(
            id=MEMORY_ID, actorId=user_id, sessionId=session_id, page=1, size=100
        )
        items = _sort_events_asc(_list_data(resp))  # tăng dần → loadSession render đúng trình tự
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] list_events lỗi: {exc}")
        return {"events": []}

    events: list[dict] = []
    for ev in items:
        payload = getattr(ev, "payload", None)
        role = getattr(payload, "role", None) if payload else None
        msg = getattr(payload, "message", None) if payload else None
        ts = getattr(ev, "event_timestamp", None)
        if msg:
            events.append({"role": role or "assistant", "text": msg, "ts": ts})
    return {"events": events}


async def _delete_session(mem, user_id: str, session_id: str) -> dict:
    """Xóa cả 1 phiên hội thoại. Memory API KHÔNG có endpoint xóa cấp session →
    lặp liệt kê + xóa từng event qua `delete_event_async`. Trả về số event đã xóa.
    """
    if mem is None or not session_id:
        return {"deleted": 0, "success": False}
    deleted = 0
    try:
        # Mỗi vòng lấy 1 trang (page=1) — đã xóa nên trang kế tự dịch vào page=1.
        while True:
            resp = await mem.list_events_async(
                id=MEMORY_ID, actorId=user_id, sessionId=session_id, page=1, size=100
            )
            items = _list_data(resp)
            ids = [getattr(ev, "id", None) for ev in items]
            ids = [i for i in ids if i]
            if not ids:
                break
            progressed = False
            for eid in ids:
                try:
                    await mem.delete_event_async(
                        id=MEMORY_ID, actorId=user_id, sessionId=session_id, eventId=eid
                    )
                    deleted += 1
                    progressed = True
                except Exception as exc:  # noqa: BLE001
                    print(f"[agent] delete_event lỗi ({eid}): {exc}")
            # Không xóa được gì (tránh loop vô hạn) hoặc trang chưa đầy → dừng.
            if not progressed or len(ids) < 100:
                break
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] delete_session lỗi: {exc}")
        return {"deleted": deleted, "success": False}
    return {"deleted": deleted, "success": True}


async def _chat_stream(
    message: str,
    user_id: str,
    session_id: str,
    skill_type: str = "",
    explain_query: dict | None = None,
):
    """Async generator: stream token chat (SDK bọc thành SSE).

    Yield `{"type":"delta","text":...}` cho mỗi token và `{"type":"done"}` cuối stream.
    Header thiếu (khi memory bật) → yield 1 chunk lỗi. Recall + ghi event user trước,
    ghi event assistant (full) sau khi stream xong.

    `skill_type="explain"` (data point dashboard): nhúng playbook explain vào system prompt.
    `explain_query` (tham số truy xuất từ FE) → PREFETCH TẤT ĐỊNH dữ liệu thật đúng lát cắt
    của data point (get_cluster_detail nếu có cluster_id, ngược lại get_mentions) TRƯỚC khi
    trả lời → câu giải thích LUÔN bám mention/số liệu thật, không để router đoán/answer chay.
    """
    use_memory = memory_enabled()
    if use_memory and (not user_id or not session_id):
        missing = []
        if not user_id:
            missing.append("X-GreenNode-AgentBase-User-Id")
        if not session_id:
            missing.append("X-GreenNode-AgentBase-Session-Id")
        yield {"type": "delta", "text": f"Thiếu header bắt buộc cho memory: {', '.join(missing)}."}
        yield {"type": "done"}
        return

    if not message:
        yield {"type": "delta", "text": "Bạn hãy nhập câu hỏi nhé."}
        yield {"type": "done"}
        return

    # Tạo memory client best-effort: local thiếu GREENNODE creds → degrade, KHÔNG vỡ stream.
    mem = None
    if use_memory:
        try:
            mem = MemoryClient()
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] MemoryClient init lỗi: {exc}")

    recall_facts = ""
    history_turns: list[Message] = []
    if mem is not None:
        # Dựng turns + recall fact TRƯỚC khi ghi event message hiện tại (tránh tự trùng).
        recall_facts = await _recall_facts(mem, user_id, message)
        history_turns = await _history_turns(mem, user_id, session_id)
        await _create_event(mem, user_id, session_id, role="user", message=message)

    system = await _get_persona()
    if skill_type == "explain":
        system += "\n\n## Nhiệm vụ: Giải thích data point dashboard\n" + await _get_explain_playbook()
    if recall_facts:
        system += "\n\n## Ngữ cảnh từ bộ nhớ (dùng nếu liên quan)\n" + recall_facts

    # _build_client: thiếu API_KEY/BASE_URL/MINIMAX_MODEL → báo lỗi rõ thay vì vỡ SSE.
    try:
        llm = _build_client()
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] build client lỗi: {exc}")
        yield {"type": "delta", "text": "Chat chưa được cấu hình đúng (thiếu API_KEY/BASE_URL/MINIMAX_MODEL)."}
        yield {"type": "done"}
        return

    # Gom dữ liệu tool (dùng chung cho prefetch explain lẫn tool loop bên dưới).
    charts = None
    tool_contexts: list[str] = []
    seen_calls: set[str] = set()
    decision: dict = {"action": "answer"}

    eq = explain_query or {}
    if skill_type == "explain" and eq and runtime1_configured():
        # EXPLAIN: PREFETCH TẤT ĐỊNH dữ liệu thật đúng lát cắt của data point (FE đã suy ra
        # params) → câu giải thích bám mention/số liệu thật. KHÔNG chạy router (tránh answer
        # chay/đoán sai khoảng ngày). Lỗi prefetch → vẫn trả lời, nêu rõ giới hạn (playbook).
        tool, params = _explain_tool(eq)
        if tool:
            yield {"type": "status", "text": f"🔍 Đang truy dữ liệu: {_TOOL_LABELS.get(tool, tool)}…"}
            try:
                res = await _rt1_post(f"/query/{tool}", params)
                data = (res or {}).get("data") or {}
                if data.get("charts"):
                    charts = data["charts"]
                tool_contexts.append(_format_tool_result(tool, data))
            except Exception as exc:  # noqa: BLE001 — degrade an toàn, không vỡ stream
                print(f"[agent] explain prefetch {tool} lỗi: {exc}")
                tool_contexts.append(f"[Prefetch {tool}: chưa truy được dữ liệu từ hệ thống.]")
    # Vòng điều phối tool/skill (D4) cho chat thường — chỉ khi RT1 sẵn sàng. Lỗi/parse fail → answer.
    elif runtime1_configured():
        decision = await _route_decision(llm, history_turns, message)

    # Skill (nhận diện ý định viết nội dung) → sinh qua RT1 /generate, stream content.
    if decision.get("action") == "skill" and decision.get("skill_type") in _SKILL_LABELS:
        cluster_id = decision.get("cluster_id")
        context = await _history_text(mem, user_id, session_id) if mem is not None else ""
        body: dict = {"type": decision["skill_type"], "context": context, "session_id": session_id}
        if cluster_id is not None:
            body["cluster_id"] = cluster_id
        parts: list[str] = []
        try:
            async for delta in _rt1_post_stream("/generate/stream", body):
                parts.append(delta)
                yield {"type": "delta", "text": delta}
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] skill /generate/stream (intent) lỗi: {exc}")
        full = "".join(parts).strip()
        if not full:
            full = "Xin lỗi, hiện chưa sinh được nội dung. Bạn thử lại sau nhé."
            yield {"type": "delta", "text": full}
        if mem is not None:
            await _create_event(mem, user_id, session_id, role="assistant", message=full)
        yield {"type": "done"}
        return

    # Tool LOOP (cần số liệu/danh sách): gọi RT1 /query/{tool}, hỏi router bước kế (kèm dữ
    # liệu đã truy) → gọi tiếp hay trả lời. Tối đa MAX_TOOL_ROUNDS vòng → "truy vấn RỒI trả
    # lời". Phát chip trạng thái trước mỗi tool; chống lặp tool+params y hệt; lỗi → dừng truy.
    # (explain prefetch ở trên đã set decision="answer" → vòng này bỏ qua ngay.)
    for _round in range(MAX_TOOL_ROUNDS):
        if decision.get("action") != "tool" or not decision.get("tool"):
            break
        tool = decision["tool"]
        params = decision.get("params") or {}
        sig = tool + json.dumps(params, sort_keys=True, ensure_ascii=False)
        if sig in seen_calls:
            break  # router lặp y hệt → tránh vòng lặp vô ích, sang trả lời
        seen_calls.add(sig)
        yield {"type": "status", "text": f"🔍 Đang truy dữ liệu: {_TOOL_LABELS.get(tool, tool)}…"}
        try:
            res = await _rt1_post(f"/query/{tool}", params)
            data = (res or {}).get("data") or {}
            if data.get("charts"):
                charts = data["charts"]  # giữ chart mới nhất cho FE
            tool_contexts.append(_format_tool_result(tool, data))
        except Exception as exc:  # noqa: BLE001 — degrade an toàn, không vỡ stream
            print(f"[agent] tool {tool} lỗi: {exc}")
            tool_contexts.append(f"[Tool {tool}: chưa truy được dữ liệu từ hệ thống.]")
            break  # lỗi → dừng truy, trả lời với dữ liệu đang có (không bịa)
        # Hỏi router bước kế: đủ dữ liệu → answer; cần thêm → tool khác.
        decision = await _route_decision(llm, history_turns, message, tool_contexts)

    # [system] + working memory + [user] (+ TOÀN BỘ dữ liệu tool đã gom nếu có).
    messages = [Message("system", [system]), *history_turns, Message("user", [message])]
    if tool_contexts:
        messages.append(
            Message(
                "user",
                [
                    "## Dữ liệu đã truy được (diễn giải bằng tiếng Việt, BÁM SÁT số liệu này; "
                    "KHÔNG gọi thêm tool, KHÔNG in cú pháp gọi hàm/`<FunctionCall>` — dữ liệu đã đủ ở đây)\n"
                    + "\n\n".join(tool_contexts)
                ],
            )
        )

    full = ""
    try:
        async for delta in stream_text(llm, messages):
            full += delta
            yield {"type": "delta", "text": delta}
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] stream lỗi: {type(exc).__name__}: {exc}")
        if not full:
            yield {
                "type": "delta",
                "text": f"Xin lỗi, dịch vụ trả lời đang gặp sự cố ({type(exc).__name__}). Bạn thử lại sau nhé.",
            }

    if full and mem is not None:
        await _create_event(mem, user_id, session_id, role="assistant", message=full)
    done: dict = {"type": "done"}
    if charts:
        done["charts"] = charts  # FE gắn vào ChatMessage cuối lượt
    yield {**done}


_SKILL_LABELS = {
    # 3 skill chat tự do (nhận diện ý định trong chat).
    "content": "Viết content",
    "design_brief": "Brief thiết kế",
    "response_plan": "Kế hoạch ứng phó",
    # 5 skill Monitor revise-từ-chat — bám nhãn TabBar Monitor để chip trạng thái nhất quán.
    "narrative": "Report",
    "root_cause": "Nguyên nhân",
    "response_strategy": "Chiến lược",
    "brand_voice": "Brand voice",
    "seeding_comments": "Seeding",
}


async def _skill_stream(
    skill_type: str,
    cluster_id,
    user_id: str,
    session_id: str,
    user_prompt: str = "",
    base_content: str = "",
):
    """Sinh/revise nội dung qua RT1 /generate/stream (3 skill chat + 5 skill Monitor) rồi
    stream về như chat turn.

    `user_prompt` = mô tả người dùng gõ kèm khi chọn skill (đối tượng, kênh, giọng điệu…)
    → đưa vào `instruction` (yêu cầu cụ thể, ưu tiên tuyệt đối ở RT1). RT2 KHÔNG ghi Mongo —
    RT1 lo lưu monitor_artifacts (created_by="chat").

    `base_content` (D7/D8): nội dung gốc đã GHIM khi "Gửi sang Chat" một artifact Monitor —
    đính lại MỖI lượt follow-up (race-free, độc lập cửa sổ memory). Khi có → đóng khung
    `context` TƯỜNG MINH (nội dung gốc + nhãn skill + cụm) đặt TRƯỚC lịch sử phiên. Khi
    không có (skill từ nhận-diện-ý-định) → degrade về `_history_text` như cũ.
    """
    if skill_type not in _SKILL_LABELS:
        yield {"type": "delta", "text": f"Skill không hợp lệ: {skill_type}."}
        yield {"type": "done"}
        return
    if not runtime1_configured():
        yield {"type": "delta", "text": "Chưa cấu hình Runtime 1 (RUNTIME1_BASE_URL) để sinh nội dung."}
        yield {"type": "done"}
        return

    mem = None
    if memory_enabled():
        try:
            mem = MemoryClient()
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] MemoryClient init lỗi: {exc}")

    history_text = await _history_text(mem, user_id, session_id) if mem is not None else ""
    base_content = (base_content or "").strip()
    user_prompt = (user_prompt or "").strip()

    # D8: có base_content → đóng khung context tường minh (nội dung gốc + skill + cụm) đặt
    # TRƯỚC lịch sử; truncate base theo trần MESSAGE_MAX_CHARS để không nuốt prompt. Thiếu
    # base_content → degrade về lịch sử phiên như cũ (đường intent tự do, không lỗi).
    if base_content:
        label = _SKILL_LABELS.get(skill_type, skill_type)
        where = f"cụm #{cluster_id}" if cluster_id is not None else "không gắn cụm"
        context = (
            f"## Nội dung gốc cần chỉnh sửa (skill: {label}, {where})\n"
            f"{base_content[:MESSAGE_MAX_CHARS]}"
        )
        if history_text:
            context += (
                "\n\n## Lịch sử hội thoại phiên (các bản chỉnh trước, nếu có)\n" + history_text
            )
    else:
        context = history_text

    # `instruction` = prompt người dùng (yêu cầu cụ thể, ưu tiên tuyệt đối ở RT1) —
    # tách KHỎI `context` (lịch sử/artifact) để không bị coi là dữ liệu nền rồi bỏ qua.
    body: dict = {
        "type": skill_type,
        "context": context,
        "instruction": user_prompt,
        "session_id": session_id,
    }
    if cluster_id is not None:
        body["cluster_id"] = cluster_id
    parts: list[str] = []
    try:
        async for delta in _rt1_post_stream("/generate/stream", body):
            parts.append(delta)
            yield {"type": "delta", "text": delta}
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] skill /generate/stream lỗi: {type(exc).__name__}: {exc}")
        if not parts:
            yield {
                "type": "delta",
                "text": "Xin lỗi, hiện chưa sinh được nội dung (dịch vụ sinh nội dung gặp sự cố). Bạn thử lại sau nhé.",
            }
            yield {"type": "done"}
            return

    content = "".join(parts).strip() or "(không sinh được nội dung)"

    if mem is not None:
        user_msg = (
            f"[{_SKILL_LABELS[skill_type]}] {user_prompt}".strip()
            if user_prompt
            else f"[Yêu cầu: {_SKILL_LABELS[skill_type]}]"
        )
        await _create_event(mem, user_id, session_id, role="user", message=user_msg)
        await _create_event(mem, user_id, session_id, role="assistant", message=content)
    yield {"type": "done"}


async def handler_async(payload: dict, user_id: str, session_id: str):
    """Định tuyến theo `kind`. Chat turn → trả async-generator (SSE); còn lại → dict (JSON)."""
    kind = (payload or {}).get("kind")
    use_memory = memory_enabled()
    mem = None
    if use_memory:
        try:
            mem = MemoryClient()
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] MemoryClient init lỗi: {exc}")

    if kind == "context_inject":
        return await _context_inject(mem, user_id, session_id, payload)
    if kind == "list_sessions":
        return await _list_sessions(mem, user_id)
    if kind == "list_events":
        sid = (payload.get("session_id") or session_id or "").strip()
        return await _list_events(mem, user_id, sid)
    if kind == "delete_session":
        sid = (payload.get("session_id") or session_id or "").strip()
        return await _delete_session(mem, user_id, sid)
    if kind == "skill":
        # Skill người dùng chọn (3 skill chat + 5 skill Monitor revise) + prompt mô tả mong
        # muốn (message) → stream SSE. Prompt là yêu cầu cụ thể (instruction) đưa vào sinh.
        # `base_content` (D7): nội dung gốc đã ghim khi revise một artifact Monitor.
        skill_type = (payload.get("skill_type") or "").strip()
        cluster_id = payload.get("cluster_id")
        user_prompt = (payload.get("message") or "").strip()
        base_content = (payload.get("base_content") or "").strip()
        # "explain" (data point dashboard) KHÔNG đi đường sinh nội dung RT1 — chạy chat-stream
        # với playbook explain + tool-calling sẵn có (AI tự truy số liệu slice).
        if skill_type == "explain":
            explain_query = payload.get("explain_query") or None
            return _chat_stream(
                user_prompt, user_id, session_id, skill_type="explain", explain_query=explain_query
            )
        # skill_type ngoài 3 chat + 5 Monitor → _skill_stream trả "skill không hợp lệ", không gọi RT1.
        return _skill_stream(
            skill_type, cluster_id, user_id, session_id, user_prompt, base_content
        )

    # Chat turn: trả async generator (KHÔNG await) → SDK stream SSE.
    message = (payload or {}).get("message", "").strip()
    return _chat_stream(message, user_id, session_id)


@app.entrypoint
async def handler(payload: dict, context: RequestContext):
    """POST /invocations. Chat → SSE stream; context_inject/list_* → JSON.

    Trả async-generator → SDK bọc StreamingResponse(text/event-stream); trả dict → JSON.
    """
    user_id = (getattr(context, "user_id", None) or (payload or {}).get("user_id") or "").strip()
    session_id = (
        getattr(context, "session_id", None) or (payload or {}).get("session_id") or ""
    ).strip()
    return await handler_async(payload or {}, user_id, session_id)


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(port=port, host="0.0.0.0")
