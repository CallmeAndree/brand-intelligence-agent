"use client";

import { useEffect, useRef, useState } from "react";
import ChatMessageBubble from "./ChatMessageBubble";
import ChatInput from "./ChatInput";
import ChatHistorySidebar from "./ChatHistorySidebar";
import ChatContextBanner, { type ActiveChatContext } from "./ChatContextBanner";
import {
  sendMessageStream,
  resetSession,
  takeQueuedContextInject,
  takeQueuedExplainContext,
  buildExplainPrompt,
  buildExplainQuery,
  sendContextInject,
  type SendOptions,
} from "@/lib/chat";
import type { Alert, ArtifactType, ChatMessage, EChartSpec } from "@/lib/types";

const GREETING: ChatMessage = {
  role: "assistant",
  text: "Chào bạn 👋 Mình là Zalopay 505 Analyst. Hỏi mình về các mention tiêu cực của Zalopay nhé.",
};

// Nhãn 5 skill Monitor — bám nhãn TabBar Monitor workspace (chip "Đang revise").
const MONITOR_LABELS: Record<ArtifactType, string> = {
  narrative: "Report",
  root_cause: "Nguyên nhân",
  response_strategy: "Chiến lược",
  brand_voice: "Brand voice",
  seeding_comments: "Seeding",
};

// Trích đoạn ngắn từ markdown (bỏ ký hiệu) làm preview cho banner ngữ cảnh.
function previewOf(md: string, max = 160): string {
  const plain = md
    .replace(/[#*_>`~|-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return plain.length > max ? `${plain.slice(0, max)}…` : plain;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  // `sending` = chỉ trước token ĐẦU (hiện chấm typing); tắt ngay khi token đầu về.
  const [sending, setSending] = useState(false);
  // `busy` = bận TOÀN BỘ lượt trả lời (từ lúc gửi tới khi stream kết thúc) → khoá ô nhập +
  // skill suốt quá trình stream, chặn người dùng gửi chèn prompt mới (như các agent khác).
  const [busy, setBusy] = useState(false);
  // Chip transient khi agent đang gọi tool ("🔍 Đang truy dữ liệu: …"); clear khi token đầu về.
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false); // panel mobile
  const [reloadKey, setReloadKey] = useState(0); // bump → sidebar reload danh sách
  // Cụm vừa nạp ngữ cảnh (inject/alert) → quick-action skill gắn cluster_id + nổi bật.
  const [skillCluster, setSkillCluster] = useState<number | null>(null);
  const [skillHighlight, setSkillHighlight] = useState(false);
  // Mỏ neo revise Monitor (D7): nội dung gốc + skill_type + cụm của artifact "Gửi sang Chat".
  // Khi set → MỖI lượt follow-up gửi kèm base_content (race-free, độc lập memory window).
  const [monitorBase, setMonitorBase] = useState<{
    skill_type: ArtifactType;
    cluster_id: number | null;
    content_md: string;
  } | null>(null);
  // Ngữ cảnh hiển thị trực quan trên banner cố định (đang phân tích cụm nào).
  const [activeContext, setActiveContext] = useState<ActiveChatContext | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Bỏ ngữ cảnh: gỡ banner + ngừng gắn cluster vào skill + hạ nổi bật.
  const clearContext = () => {
    setActiveContext(null);
    setSkillCluster(null);
    setSkillHighlight(false);
  };

  // auto-scroll xuống cuối khi có message mới hoặc đang gõ.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, sending]);

  // Nếu đến từ Monitor "Gửi sang Chat": nạp artifact làm ngữ cảnh (ghi memory) 1 lần.
  // Banner cố định thay cho bubble trôi → người dùng luôn thấy đang phân tích cụm nào.
  useEffect(() => {
    const inject = takeQueuedContextInject();
    if (!inject) return;
    setActiveContext({
      clusterId: inject.cluster_id,
      source: "monitor",
      preview: previewOf(inject.content_md),
    });
    setSkillCluster(inject.cluster_id);
    setSkillHighlight(true);
    // skill_type thuộc 5 skill Monitor → GHIM mỏ neo revise (giữ content_md, không vứt).
    // Inject mới ghi đè mỏ neo cũ (đến từ artifact khác → đổi base). Inject cũ không có
    // skill_type → bỏ qua (chỉ nạp context như trước).
    if (inject.skill_type && inject.skill_type in MONITOR_LABELS) {
      setMonitorBase({
        skill_type: inject.skill_type,
        cluster_id: inject.cluster_id,
        content_md: inject.content_md,
      });
    }
    void sendContextInject(inject).catch(() => undefined);
  }, []);

  const handleSend = async (text: string, opts?: SendOptions) => {
    setMessages((prev) => [...prev, { role: "user", text }]);
    setBusy(true); // khoá ô nhập + skill suốt cả lượt (chỉ mở lại ở `finally`)
    setSending(true); // hiện typing-dots tới khi token đầu về
    // acc = TOÀN BỘ text đã nhận (tích lũy JS thuần → race-free).
    let acc = "";
    let got = false;
    // Upsert bubble assistant cuối lượt = textVal (+ charts khi có). Updater THUẦN
    // (set theo `prev` thật), không đọc biến mutable lúc flush.
    const renderAssistant = (textVal: string, charts?: EChartSpec[]) => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = { ...last, text: textVal, ...(charts ? { charts } : {}) };
        } else {
          next.push({ role: "assistant", text: textVal, ...(charts ? { charts } : {}) });
        }
        return next;
      });
    };
    const appendDelta = (delta: string) => {
      acc += delta;
      got = true;
      setSending(false);
      setToolStatus(null); // token trả lời bắt đầu → ẩn chip truy vấn
      renderAssistant(acc); // preview token-by-token
    };
    try {
      const { text: full, charts } = await sendMessageStream(text, appendDelta, opts, setToolStatus);
      // Stream kết thúc mà không nhận delta nào → vẫn hiện 1 bubble báo lỗi.
      if (!got && !full) {
        appendDelta("Xin lỗi, hiện chưa nhận được câu trả lời. Bạn thử lại nhé.");
      } else if (full || charts) {
        // CHỐT bản cuối = full (text server tích lũy, race-free) + đính charts (nếu có).
        // Dù preview giữa chừng có render sót delta nào thì kết quả cuối vẫn ĐẦY ĐỦ.
        renderAssistant(full || acc, charts);
      }
    } catch {
      if (!got) appendDelta("Không kết nối được tới dịch vụ trả lời. Bạn thử lại nhé.");
    } finally {
      setSending(false);
      setBusy(false); // stream kết thúc → mở lại ô nhập + skill
      setToolStatus(null);
      setReloadKey((k) => k + 1); // phiên có thể vừa được tạo → cập nhật danh sách
    }
  };

  // Nếu đến từ Dashboard "✨ Giải thích": phiên đã reset trước điều hướng (4.3) → set banner
  // ngữ cảnh data point + auto-gửi prompt explain (skill_type) để AI phân tích ngay (mirror
  // onPickAlert). Hội thoại tự lưu memory → hiện trong ChatHistorySidebar như mọi phiên.
  useEffect(() => {
    const ctx = takeQueuedExplainContext();
    if (!ctx) return;
    setActiveContext({
      source: "dashboard",
      dimension: ctx.dimension,
      label: ctx.label,
      value: ctx.value,
      metric: ctx.metric,
      metric2: ctx.metric2, // risk: hiện pill số thứ hai (severity TB). cluster_id giữ trong ctx cho prompt.
    });
    // explain_query: tham số truy xuất CHÍNH XÁC lát cắt của điểm → RT2 prefetch dữ liệu thật.
    void handleSend(buildExplainPrompt(ctx), {
      kind: "skill",
      skill_type: "explain",
      explain_query: buildExplainQuery(ctx),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const newSession = () => {
    resetSession();
    setMessages([GREETING]);
    clearContext();
    setSelectedSkill(null);
    setMonitorBase(null);
    setReloadKey((k) => k + 1);
  };

  // Mở lại phiên cũ từ sidebar: dựng lại messages từ event của phiên (gỡ banner + mỏ neo).
  const onLoadMessages = (msgs: ChatMessage[]) => {
    setActiveContext(null);
    setMonitorBase(null);
    setMessages(msgs.length > 0 ? msgs : [GREETING]);
  };

  // Chọn alert từ sidebar: nạp brief làm ngữ cảnh (banner) + seed câu hỏi xử lý.
  const onPickAlert = async (alert: Alert) => {
    setActiveContext({
      clusterId: alert.cluster_id,
      source: "alert",
      department: alert.department,
      preview: previewOf(alert.brief_md),
    });
    await sendContextInject({
      content_md: alert.brief_md,
      cluster_id: alert.cluster_id,
    }).catch(() => undefined);
    setSkillCluster(alert.cluster_id);
    setSkillHighlight(true);
    await handleSend(`Phân tích & đề xuất xử lý cảnh báo cụm #${alert.cluster_id}`);
  };

  // Skill = CHỌN để nạp (không chạy ngay). Người dùng bấm → skill được "trang bị",
  // gõ thêm prompt mô tả mong muốn rồi mới gửi → sinh nội dung theo skill + prompt đó.
  type SkillType = "content" | "design_brief" | "response_plan";
  const SKILLS: { type: SkillType; label: string; hint: string }[] = [
    { type: "content", label: "Viết nội dung truyền thông", hint: "nội dung truyền thông" },
    { type: "design_brief", label: "Xây dựng yêu cầu thiết kế", hint: "yêu cầu thiết kế" },
    { type: "response_plan", label: "Lên kế hoạch ứng phó", hint: "kế hoạch ứng phó" },
  ];
  const [selectedSkill, setSelectedSkill] = useState<SkillType | null>(null);
  const selectedSkillMeta = SKILLS.find((s) => s.type === selectedSkill) ?? null;

  // Bấm 1 skill chat tự do: trang bị (toggle nếu bấm lại chính nó). KHÔNG gửi/sinh ngay.
  // D3: nếu đang ở mode revise Monitor → gỡ mỏ neo + ngữ cảnh artifact Monitor (chuyển hẳn
  // sang luồng chat tự do, tránh trộn context gây output lai).
  const toggleSkill = (skill_type: SkillType) => {
    if (monitorBase) {
      setMonitorBase(null);
      clearContext();
    }
    setSelectedSkill((prev) => (prev === skill_type ? null : skill_type));
  };

  // Người dùng gửi từ ô nhập:
  // - Mode revise Monitor (monitorBase) ưu tiên (D7): gửi kind="skill" với skill_type Monitor
  //   + cluster_id + base_content (đính LẠI mỗi lượt → bám đúng nội dung gốc đã ghim).
  // - Ngược lại, đang trang bị skill chat tự do → gửi kind="skill" theo selectedSkill (D2).
  // - Không có gì → chat thường.
  const onUserSend = (text: string) => {
    if (busy) return; // đang stream → bỏ qua (ô nhập đã disabled, đây là chốt phòng thủ)
    if (monitorBase) {
      void handleSend(text, {
        kind: "skill",
        skill_type: monitorBase.skill_type,
        cluster_id: monitorBase.cluster_id ?? undefined,
        base_content: monitorBase.content_md,
      });
      return;
    }
    if (selectedSkill) {
      void handleSend(text, {
        kind: "skill",
        skill_type: selectedSkill,
        cluster_id: skillCluster ?? undefined,
      });
      return;
    }
    void handleSend(text);
  };

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-4">
      {/* Sidebar cố định (desktop ≥ lg) */}
      <aside className="hidden w-72 shrink-0 overflow-hidden rounded-2xl border border-ink/10 bg-white/40 lg:flex lg:flex-col">
        <ChatHistorySidebar
          onLoadMessages={onLoadMessages}
          onPickAlert={onPickAlert}
          onNewSession={newSession}
          reloadKey={reloadKey}
        />
      </aside>

      {/* Panel lịch sử thu gọn (mobile < lg) */}
      {historyOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div className="absolute inset-0 bg-ink/20" onClick={() => setHistoryOpen(false)} />
          <aside className="relative flex h-full w-full max-w-xs flex-col border-r border-ink/10 bg-canvas shadow-lg">
            <div className="flex items-center justify-between border-b border-ink/10 px-4 py-3">
              <h2 className="text-title-sm text-ink">Lịch sử</h2>
              <button
                onClick={() => setHistoryOpen(false)}
                className="rounded-full px-2 text-lg text-ink/40 hover:text-ink"
                aria-label="Đóng"
              >
                ×
              </button>
            </div>
            <ChatHistorySidebar
              onLoadMessages={onLoadMessages}
              onPickAlert={onPickAlert}
              onNewSession={newSession}
              onAfterPick={() => setHistoryOpen(false)}
              reloadKey={reloadKey}
            />
          </aside>
        </div>
      )}

      {/* Cột chat */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setHistoryOpen(true)}
              className="rounded-xl border border-ink/15 px-3 py-1.5 text-button text-ink/70 transition hover:bg-white/60 lg:hidden"
              aria-label="Mở lịch sử"
            >
              ☰
            </button>
            <h1 className="text-title-lg">Chat Analyst</h1>
          </div>
          <button
            onClick={newSession}
            className="rounded-xl border border-ink/15 px-3 py-1.5 text-button text-ink/70 transition hover:bg-white/60 lg:hidden"
          >
            Phiên mới
          </button>
        </div>

        <ChatContextBanner context={activeContext} onClear={clearContext} />

        <div
          ref={scrollRef}
          className="flex-1 space-y-3 overflow-y-auto rounded-2xl border border-ink/10 bg-white/40 p-4"
        >
          {messages.map((m, i) => (
            <ChatMessageBubble key={i} message={m} />
          ))}
          {/* Chip truy vấn (agent đang gọi tool) — ưu tiên hiện thay chấm đang-gõ. */}
          {toolStatus && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-2xl border border-feature-lavender/40 bg-feature-lavender/15 px-4 py-2.5 text-body-sm text-ink/70">
                <span className="inline-flex gap-1" aria-hidden>
                  <span className="animate-bounce">•</span>
                  <span className="animate-bounce [animation-delay:0.15s]">•</span>
                  <span className="animate-bounce [animation-delay:0.3s]">•</span>
                </span>
                <span className="truncate">{toolStatus}</span>
              </div>
            </div>
          )}
          {sending && !toolStatus && (
            <div className="flex justify-start">
              <div className="rounded-2xl border border-ink/10 bg-feature-cream px-4 py-3 text-body-md text-ink/50">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce">•</span>
                  <span className="animate-bounce [animation-delay:0.15s]">•</span>
                  <span className="animate-bounce [animation-delay:0.3s]">•</span>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Mỏ neo revise Monitor (D7): chip "Đang revise <skill> cho cụm #N". Mỗi lượt
            follow-up bám đúng nội dung gốc đã ghim. Chọn skill chat tự do hoặc bấm × để gỡ. */}
        {monitorBase && (
          <div className="mt-2 flex items-center gap-2 rounded-card border border-feature-peach/50 bg-feature-peach/20 px-3 py-2">
            <span className="text-caption font-medium text-ink/55">Đang revise</span>
            <span className="rounded-full bg-ink px-2.5 py-0.5 text-caption font-medium text-white">
              {MONITOR_LABELS[monitorBase.skill_type]}
            </span>
            {monitorBase.cluster_id != null && (
              <span className="text-caption text-ink/55">cho cụm #{monitorBase.cluster_id}</span>
            )}
            <span className="min-w-0 flex-1 truncate text-caption text-ink/45">
              — gõ yêu cầu chỉnh sửa (ngắn gọn hơn, thêm emoji…) rồi nhấn Gửi
            </span>
            <button
              type="button"
              onClick={() => {
                setMonitorBase(null);
                clearContext();
              }}
              aria-label="Bỏ revise"
              title="Bỏ revise"
              className="shrink-0 rounded-full px-2 py-0.5 text-base leading-none text-ink/35 transition hover:bg-ink/5 hover:text-ink"
            >
              ×
            </button>
          </div>
        )}

        {/* Chọn skill để TRANG BỊ (không chạy ngay). Nổi bật khi đã nạp ngữ cảnh. */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-caption font-medium text-ink/50">
            {activeContext?.clusterId != null
              ? `Kỹ năng cho cụm #${activeContext.clusterId}:`
              : "Kỹ năng:"}
          </span>
          {SKILLS.map((s) => {
            const armed = selectedSkill === s.type;
            return (
              <button
                key={s.type}
                type="button"
                disabled={busy}
                aria-pressed={armed}
                onClick={() => toggleSkill(s.type)}
                className={`rounded-full border px-3 py-1.5 text-button transition disabled:opacity-50 ${
                  armed
                    ? "border-ink bg-ink text-white hover:bg-ink/90"
                    : skillHighlight
                      ? "border-feature-peach bg-feature-peach/30 text-ink hover:bg-feature-peach/50"
                      : "border-ink/15 text-ink/60 hover:bg-white/60"
                }`}
              >
                {s.label}
              </button>
            );
          })}
        </div>

        {/* Chip báo skill đang trang bị: nhắc người dùng mô tả mong muốn rồi gửi. */}
        {selectedSkillMeta && (
          <div className="mt-2 flex items-center gap-2 rounded-card border border-ink/10 bg-feature-cream px-3 py-2">
            <span className="text-caption font-medium text-ink/55">Đang dùng kỹ năng</span>
            <span className="rounded-full bg-ink px-2.5 py-0.5 text-caption font-medium text-white">
              {selectedSkillMeta.label}
            </span>
            <span className="min-w-0 flex-1 truncate text-caption text-ink/45">
              — mô tả {selectedSkillMeta.hint} bạn muốn rồi nhấn Gửi
            </span>
            <button
              type="button"
              onClick={() => setSelectedSkill(null)}
              aria-label="Bỏ kỹ năng"
              title="Bỏ kỹ năng"
              className="shrink-0 rounded-full px-2 py-0.5 text-base leading-none text-ink/35 transition hover:bg-ink/5 hover:text-ink"
            >
              ×
            </button>
          </div>
        )}

        <div className="mt-3">
          <ChatInput
            onSend={onUserSend}
            disabled={busy}
            placeholder={
              busy
                ? "Đang trả lời, vui lòng đợi…"
                : monitorBase
                  ? `Yêu cầu chỉnh "${MONITOR_LABELS[monitorBase.skill_type]}" (ngắn gọn hơn, thêm emoji, đổi giọng…)…`
                  : selectedSkillMeta
                    ? `Mô tả ${selectedSkillMeta.hint} bạn muốn (đối tượng, kênh, giọng điệu…)…`
                    : "Hỏi về mention tiêu cực của Zalopay…"
            }
          />
        </div>
      </div>
    </div>
  );
}
