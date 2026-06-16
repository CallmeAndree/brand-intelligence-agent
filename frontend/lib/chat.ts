"use client";

import type { ArtifactType, ChatMessage, ChatSessionSummary, EChartSpec, Filters } from "./types";

// Tùy chọn cho 1 lượt gửi: skill (quick-action sinh nội dung / giải thích / revise Monitor)
// + cluster_id ngữ cảnh. `skill_type` gồm 3 skill chat tự do, "explain", và 5 skill Monitor
// (ArtifactType) cho revise-từ-chat. `base_content` = nội dung gốc ghim (D7) đính mỗi lượt.
export interface SendOptions {
  kind?: "skill";
  skill_type?: ArtifactType | "content" | "design_brief" | "response_plan" | "explain";
  cluster_id?: number;
  base_content?: string;
  // Explain (D-explain): tham số truy xuất CHÍNH XÁC lát cắt đứng sau data point (from/to +
  // dimension→param). RT2 dùng để prefetch dữ liệu THẬT (tất định) thay vì để router đoán →
  // câu giải thích luôn bám mention/số liệu thật, không nói chung chung.
  explain_query?: ExplainQuery;
}

// Tham số máy-đọc-được cho 1 lần explain — suy ra từ ExplainContext + filter dashboard.
export interface ExplainQuery {
  from?: string;
  to?: string;
  product_area?: string;
  platform?: string;
  text_contains?: string;
  cluster_id?: number | string;
  keyword_group_id?: number;
}

// Kết quả 1 lượt stream: full text + charts (nếu tool chuỗi thời gian trả về ở chunk done).
export interface StreamResult {
  text: string;
  charts?: EChartSpec[];
}

// Slice sơ: session client-side. session_id ổn định trong phiên trình duyệt
// (localStorage), user_id cố định cho demo. Payload mang sẵn cả hai để backend
// sau (Runtime 2 AgentBase) đọc được — slice này chưa dùng để personalize.

const SESSION_KEY = "bi_chat_session_id";
const DEMO_USER_ID = "demo";

export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function getUserId(): string {
  return DEMO_USER_ID;
}

// Bắt đầu phiên mới (nút "phiên mới").
export function resetSession(): string {
  const id = crypto.randomUUID();
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

// Gửi message tới proxy /api/chat. Proxy luôn trả ChatMessage (kể cả lỗi → text
// thông báo), nên chỉ ném khi network/parse hỏng hoàn toàn.
export async function sendMessage(message: string): Promise<ChatMessage> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: getSessionId(),
      user_id: getUserId(),
      message,
    }),
  });
  const data = (await res.json()) as ChatMessage;
  return { ...data, role: "assistant", text: data.text ?? "" };
}

// Gửi message dạng STREAM. Đọc SSE pass-through từ Runtime 2 (qua proxy /api/chat),
// gọi onDelta cho mỗi token, trả full text khi xong. Khung SSE của SDK: chỉ `data: {json}`
// với json = {type:"delta",text} | {type:"done"} | {error,...}. Fallback: proxy trả JSON
// (lỗi/timeout) → đọc 1 phát, coi text như 1 delta.
export async function sendMessageStream(
  message: string,
  onDelta: (text: string) => void,
  opts: SendOptions = {},
  onStatus?: (text: string) => void,
): Promise<StreamResult> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: getSessionId(),
      user_id: getUserId(),
      message,
      ...opts,
    }),
  });

  const ctype = res.headers.get("content-type") ?? "";
  // Proxy degrade thành JSON (lỗi/timeout) → không phải stream. JSON có thể kèm charts.
  if (!res.body || !ctype.includes("text/event-stream")) {
    const data = (await res.json().catch(() => null)) as ChatMessage | null;
    const text = data?.text ?? "Không kết nối được tới dịch vụ trả lời. Bạn thử lại nhé.";
    onDelta(text);
    return { text, charts: data?.charts };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let full = "";
  let charts: EChartSpec[] | undefined;

  const handleData = (data: string) => {
    if (!data) return;
    let obj: {
      type?: string;
      text?: string;
      error?: string;
      message?: string;
      charts?: EChartSpec[];
    };
    try {
      obj = JSON.parse(data);
    } catch {
      return;
    }
    if (obj.error) {
      const t = `\n\n[Lỗi: ${obj.message || obj.error}]`;
      full += t;
      onDelta(t);
      return;
    }
    // Chunk trạng thái (agent đang gọi tool): hiện chip transient, KHÔNG cộng vào text.
    if (obj.type === "status") {
      onStatus?.(obj.text ?? "");
      return;
    }
    if (obj.type === "delta" && obj.text) {
      full += obj.text;
      onDelta(obj.text);
    }
    // Chunk cuối (type:"done") có thể mang charts (tool get_trend/compare_periods).
    if (obj.type === "done" && obj.charts?.length) {
      charts = obj.charts;
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      handleData(dataLines.join("\n"));
    }
  }
  return { text: full, charts };
}

// ---- Lịch sử hội thoại (memory List Sessions/Events) ----

// Liệt kê các phiên hội thoại cũ của actor hiện tại.
export async function listSessions(): Promise<ChatSessionSummary[]> {
  const res = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(getUserId())}`);
  if (!res.ok) return [];
  const data = (await res.json()) as { sessions?: ChatSessionSummary[] };
  return data.sessions ?? [];
}

// Xóa 1 phiên hội thoại cũ (xóa toàn bộ event của phiên trong memory). Trả true nếu thành công.
export async function deleteSession(sid: string): Promise<boolean> {
  const res = await fetch(
    `/api/chat/sessions/${encodeURIComponent(sid)}?user_id=${encodeURIComponent(getUserId())}`,
    { method: "DELETE" },
  );
  if (!res.ok) return false;
  const data = (await res.json().catch(() => null)) as { success?: boolean } | null;
  return data?.success ?? false;
}

// Mở lại 1 phiên cũ: set session_id hiện tại + trả về danh sách message dựng từ event.
export async function loadSession(sid: string): Promise<ChatMessage[]> {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SESSION_KEY, sid);
  }
  const res = await fetch(
    `/api/chat/sessions/${encodeURIComponent(sid)}?user_id=${encodeURIComponent(getUserId())}`,
  );
  if (!res.ok) return [];
  const data = (await res.json()) as {
    events?: { role: string; text: string; ts?: string | null }[];
  };
  return (data.events ?? []).map((e) => ({
    role: e.role === "user" ? "user" : "assistant",
    // event context_inject ghi role=user với marker "[Ngữ cảnh..." (artifact cũ HOẶC nội
    // dung Monitor revise kèm skill — D9) → gắn nhãn 📎.
    text: e.text.startsWith("[Ngữ cảnh") ? `📎 ${e.text}` : e.text,
  }));
}

// ---- Cầu nối Monitor → Chat (context inject) ----
// Monitor "Gửi sang Chat" → lưu artifact tạm vào sessionStorage rồi điều hướng /chat;
// ChatWindow đọc khi mount, gửi 1 message kind="context_inject" để Runtime 2 ghi memory.
const INJECT_KEY = "bi_pending_context_inject";

export interface ContextInject {
  content_md: string;
  cluster_id: number;
  // skill_type của artifact Monitor vừa gửi (5 loại) → Chat tự trang bị skill revise đó
  // (D1). Inject cũ không có trường này vẫn chạy như trước (chỉ nạp context, không arm).
  skill_type?: ArtifactType;
}

export function queueContextInject(payload: ContextInject): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(INJECT_KEY, JSON.stringify(payload));
  }
}

export function takeQueuedContextInject(): ContextInject | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(INJECT_KEY);
  if (!raw) return null;
  window.sessionStorage.removeItem(INJECT_KEY);
  try {
    return JSON.parse(raw) as ContextInject;
  } catch {
    return null;
  }
}

// Gửi context_inject sang Runtime 2 (ghi memory). Trả ChatMessage xác nhận.
export async function sendContextInject(inject: ContextInject): Promise<ChatMessage> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: getSessionId(),
      user_id: getUserId(),
      kind: "context_inject",
      content_md: inject.content_md,
      cluster_id: inject.cluster_id,
      // D9: mang skill_type để RT2 ghi memory event kèm danh tính skill (marker).
      ...(inject.skill_type ? { skill_type: inject.skill_type } : {}),
    }),
  });
  const data = (await res.json()) as ChatMessage;
  return { ...data, role: "assistant", text: data.text ?? "" };
}

// ---- Cầu nối Dashboard → Chat (explain một data point) ----
// Click "✨ Giải thích" trên tooltip chart → đóng gói ngữ cảnh data point vào
// sessionStorage rồi điều hướng /chat; ChatWindow đọc khi mount → set banner +
// auto-gửi prompt skill_type="explain" để AI phân tích ngay. Dùng CHUNG cơ chế
// sessionStorage như đường cluster Monitor nhưng key riêng (shape/luồng tiêu thụ khác).
const EXPLAIN_KEY = "bi_pending_explain_context";

// Ngữ cảnh của một data point trên dashboard cần AI giải thích. Tổng quát hóa
// ContextInject (cluster) cho data point bất kỳ: chiều + giá trị + số liệu quan sát + filter.
export interface ExplainContext {
  source: "dashboard";
  dimension: "month" | "platform" | "product_area" | "topic" | "keyword" | "risk";
  value: string; // "2026-01" | "TikTok" | "Transfer" | "<chủ đề>" | "<từ khóa>"
  label: string; // nhãn hiển thị, vd "Tháng 01/2026"
  metric?: { name: string; value: number }; // số chart đang hiện
  // Chiều risk: data point có 2 số (volume + severity TB) → pill thứ hai trên banner + nhúng prompt.
  metric2?: { name: string; value: number };
  // Chiều topic mode=cluster → AI đào sâu qua get_cluster_detail (giữ trong ctx cho prompt, không lên banner).
  cluster_id?: number | string;
  // Chiều keyword → id nhóm từ khóa (KeywordCloud) → get_mentions lọc theo keyword_group_ids
  // (nhãn nhóm hiếm khi là chuỗi nguyên văn trong mention → text_contains literal sẽ rỗng).
  keyword_group_id?: number;
  filters?: Filters; // date range + filter dashboard đang áp
}

export function queueExplainContext(payload: ExplainContext): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(EXPLAIN_KEY, JSON.stringify(payload));
  }
}

export function takeQueuedExplainContext(): ExplainContext | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(EXPLAIN_KEY);
  if (!raw) return null;
  window.sessionStorage.removeItem(EXPLAIN_KEY);
  try {
    return JSON.parse(raw) as ExplainContext;
  } catch {
    return null;
  }
}

// Mô tả phạm vi filter dashboard đang áp (để prompt nêu rõ "trong phạm vi đang lọc").
function describeFilters(f?: Filters): string {
  if (!f) return "";
  const parts: string[] = [];
  if (f.from && f.to) parts.push(`khoảng ${f.from} → ${f.to}`);
  if (f.platform) parts.push(`nền tảng ${f.platform}`);
  if (f.productArea) parts.push(`mảng sản phẩm ${f.productArea}`);
  if (f.severityBand) parts.push(`mức độ ${f.severityBand}`);
  if (f.topic) parts.push(`chủ đề ${f.topic}`);
  if (f.intent) parts.push(`ý định ${f.intent}`);
  if (f.actionableOnly) parts.push("chỉ mention đáng xử lý");
  return parts.length ? `Phạm vi đang lọc: ${parts.join(", ")}.` : "";
}

// Sinh câu hỏi tiếng Việt cho AI từ ExplainContext: câu hỏi gọn + nhúng số liệu quan
// sát + phạm vi filter. KHÔNG lặp lại "cách trả lời" (cấu trúc/dùng tool/bám số) — phần
// đó đã nằm trong playbook explain.md (system prompt) nên prompt này chỉ là câu hỏi
// (cũng là bong bóng user hiển thị → giữ sạch).
export function buildExplainPrompt(ctx: ExplainContext): string {
  const metric = ctx.metric ? ` (${ctx.metric.name}: ${ctx.metric.value})` : "";
  const scope = describeFilters(ctx.filters);

  let head: string;
  switch (ctx.dimension) {
    case "month":
      head = `Giải thích severity của ${ctx.label}${metric}. Vì sao mức này như vậy?`;
      break;
    case "platform":
      head = `Giải thích lượng mention trên nền tảng ${ctx.value}${metric}. Vì sao nền tảng này chiếm tỷ trọng như vậy?`;
      break;
    case "product_area":
      head = `Giải thích mảng sản phẩm ${ctx.value}${metric}. Bản chất vấn đề và xu hướng ra sao?`;
      break;
    case "topic": {
      // mode=cluster → nhúng cluster_id để AI truy get_cluster_detail (get_mentions không có
      // param topic); topic thô → AI dùng text_contains/search_mentions theo tên chủ đề.
      const cl =
        ctx.cluster_id != null
          ? ` Đây là cụm #${ctx.cluster_id} — dùng cluster_id này để truy chi tiết cụm.`
          : "";
      head = `Giải thích chủ đề/cụm thảo luận "${ctx.value}"${metric}. Vì sao nổi cộm, bản chất vấn đề là gì và có những mẫu mention tiêu biểu nào?${cl}`;
      break;
    }
    case "keyword":
      head = `Giải thích từ khóa "${ctx.value}"${metric}. Vì sao xuất hiện nhiều, gắn với chủ đề/sự cố nào và ngữ cảnh sử dụng ra sao?`;
      break;
    case "risk": {
      // risk: data point 2 số (volume + severity TB) → nhúng cả hai để AI luận vị trí ưu tiên.
      const m2 = ctx.metric2 ? `, ${ctx.metric2.name}: ${ctx.metric2.value}` : "";
      const both = ctx.metric ? ` (${ctx.metric.name}: ${ctx.metric.value}${m2})` : "";
      head = `Giải thích vị trí của mảng ${ctx.value}${both} trên ma trận ưu tiên xử lý. Vì sao nằm ở vị trí này và mức ưu tiên xử lý ra sao?`;
      break;
    }
    default:
      head = `Giải thích data point ${ctx.label}${metric}.`;
  }
  return [head, scope].filter(Boolean).join(" ");
}

// Ngày cuối của tháng "YYYY-MM" (vd "2026-01" → "2026-01-31"). Trả "" nếu sai định dạng.
function monthBounds(value: string): { from: string; to: string } | null {
  const m = /^(\d{4})-(\d{2})$/.exec(value);
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]); // 1-12
  if (month < 1 || month > 12) return null;
  const last = new Date(year, month, 0).getDate(); // ngày 0 của tháng kế = ngày cuối tháng này
  return { from: `${value}-01`, to: `${value}-${String(last).padStart(2, "0")}` };
}

// Suy ra tham số truy xuất CHÍNH XÁC cho 1 data point → RT2 prefetch dữ liệu thật (tất định).
// Nguyên tắc: from/to bám đúng lát cắt của điểm (tháng → biên tháng; còn lại → range filter
// đang áp để số khớp chart); dimension → đúng param lọc (product_area/platform/text_contains/
// cluster_id). Nhờ vậy explain LUÔN truy đúng dữ liệu đứng sau điểm, không để LLM đoán.
export function buildExplainQuery(ctx: ExplainContext): ExplainQuery {
  const f = ctx.filters;
  const q: ExplainQuery = {};

  // Khoảng thời gian: tháng → biên tháng; còn lại → range dashboard đang áp.
  if (ctx.dimension === "month") {
    const b = monthBounds(ctx.value);
    if (b) {
      q.from = b.from;
      q.to = b.to;
    }
  }
  if (!q.from && f?.from) q.from = f.from;
  if (!q.to && f?.to) q.to = f.to;

  // Bộ lọc theo chiều của data point (ưu tiên giá trị của chính điểm; bổ sung filter đang áp).
  if (ctx.dimension === "product_area" || ctx.dimension === "risk") q.product_area = ctx.value;
  else if (f?.productArea) q.product_area = f.productArea;

  if (ctx.dimension === "platform") q.platform = ctx.value;
  else if (f?.platform) q.platform = f.platform;

  if (ctx.dimension === "keyword") {
    // Có id nhóm → lọc CHÍNH XÁC theo keyword_group_ids (nhãn nhóm ≠ chuỗi trong mention).
    if (ctx.keyword_group_id != null) q.keyword_group_id = ctx.keyword_group_id;
    else q.text_contains = ctx.value; // fallback: keyword tự do không gắn nhóm
  }

  if (ctx.dimension === "topic") {
    if (ctx.cluster_id != null) q.cluster_id = ctx.cluster_id;
    else q.text_contains = ctx.value; // topic thô → lọc theo tên chủ đề
  }
  return q;
}
