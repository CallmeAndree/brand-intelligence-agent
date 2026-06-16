"use client";

import { useEffect, useState } from "react";
import { listSessions, loadSession, deleteSession, getSessionId } from "@/lib/chat";
import type { Alert, ChatMessage, ChatSessionSummary } from "@/lib/types";

type Tab = "sessions" | "alerts";

// Sắp xếp phiên mới nhất lên đầu (theo updated_at giảm dần; phiên thiếu mốc xuống cuối).
function sortByNewest(list: ChatSessionSummary[]): ChatSessionSummary[] {
  return [...list].sort((a, b) => {
    const ta = a.updated_at ? new Date(a.updated_at).getTime() : 0;
    const tb = b.updated_at ? new Date(b.updated_at).getTime() : 0;
    return tb - ta;
  });
}

// Icon thùng rác (lucide-style, stroke ink) — thay emoji để bám design Clay.
function TrashIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M3 6h18" />
      <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

// Nội dung danh sách lịch sử (tab Hội thoại / Thông báo) dùng chung cho
// sidebar cố định (desktop) lẫn panel thu gọn (mobile). Tự load dữ liệu.
export default function ChatHistorySidebar({
  onLoadMessages,
  onPickAlert,
  onNewSession,
  onAfterPick,
  reloadKey = 0,
}: {
  // Mở lại phiên cũ → set messages dựng từ event.
  onLoadMessages: (messages: ChatMessage[], sessionId: string) => void;
  // Chọn alert → nạp ngữ cảnh + seed câu hỏi.
  onPickAlert: (alert: Alert) => void;
  // Tạo phiên mới.
  onNewSession: () => void;
  // Gọi sau khi chọn 1 mục (để mobile đóng panel). Không bắt buộc.
  onAfterPick?: () => void;
  // Bump để buộc reload danh sách (vd sau khi tạo phiên mới / gửi message).
  reloadKey?: number;
}) {
  const [tab, setTab] = useState<Tab>("sessions");
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  // Phiên đang chờ xác nhận xóa (mở modal). null = không có modal.
  const [confirmSid, setConfirmSid] = useState<string | null>(null);
  // Toast phản hồi sau thao tác xóa; tự ẩn sau ~2.6s.
  const [toast, setToast] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const current = typeof window !== "undefined" ? getSessionId() : "";

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    let cancelled = false;
    // Stale-while-revalidate: chỉ hiện "Đang tải…" khi chưa có dữ liệu (lần đầu / đổi tab).
    // Reload do reloadKey bump (vd vừa gửi chat) → giữ nguyên list cũ, cập nhật ngầm → khỏi nháy.
    const hasData = tab === "sessions" ? sessions.length > 0 : alerts.length > 0;
    if (!hasData) setLoading(true);
    const job =
      tab === "sessions"
        ? listSessions().then((s) => {
            if (!cancelled) setSessions(sortByNewest(s));
          })
        : fetch("/api/alerts?limit=50")
            .then((r) => r.json())
            .then((j) => {
              if (!cancelled) setAlerts(j?.data ?? []);
            });
    void job.finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
    // sessions/alerts đọc để quyết định có hiện loading hay không — cố ý không đưa vào deps
    // (không muốn re-fetch khi list đổi); chỉ fetch khi đổi tab hoặc reloadKey bump.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, reloadKey]);

  const pickSession = async (sid: string) => {
    const msgs = await loadSession(sid);
    onLoadMessages(msgs, sid);
    onAfterPick?.();
  };

  const confirmDelete = async () => {
    const sid = confirmSid;
    if (!sid) return;
    setConfirmSid(null);
    setDeleting(sid);
    const ok = await deleteSession(sid);
    setDeleting(null);
    if (!ok) {
      setToast({ kind: "error", text: "Xóa hội thoại thất bại. Bạn thử lại nhé." });
      return;
    }
    setSessions((prev) => prev.filter((s) => s.session_id !== sid));
    setToast({ kind: "success", text: "Đã xóa hội thoại." });
    // Xóa đúng phiên đang mở → reset về phiên mới (parent cũng bump reloadKey).
    if (sid === current) onNewSession();
  };

  return (
    <div className="relative flex h-full flex-col">
      <button
        onClick={() => {
          onNewSession();
          onAfterPick?.();
        }}
        className="mx-4 mt-4 rounded-xl bg-feature-cream px-3 py-2 text-button text-ink transition hover:bg-feature-cream/70"
      >
        + Phiên mới
      </button>

      {/* tab pills */}
      <div className="flex gap-1.5 px-4 py-3">
        {(
          [
            ["sessions", "Hội thoại"],
            ["alerts", "Thông báo"],
          ] as [Tab, string][]
        ).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1.5 text-nav transition ${
              tab === t ? "bg-feature-cream text-ink" : "text-ink/50 hover:text-ink/80"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto px-4 pb-4">
        {loading && <p className="py-6 text-center text-body-sm text-ink/40">Đang tải…</p>}

        {!loading && tab === "sessions" && (
          sessions.length === 0 ? (
            <p className="py-6 text-center text-body-sm text-ink/40">Chưa có phiên nào.</p>
          ) : (
            sessions.map((s) => {
              const isCurrent = s.session_id === current;
              return (
                <div
                  key={s.session_id}
                  className={`group flex items-start gap-1 rounded-[12px] border p-3 transition ${
                    isCurrent
                      ? "border-feature-teal bg-feature-teal/10"
                      : "border-ink/10 bg-white/50 hover:bg-feature-cream/50"
                  }`}
                >
                  <button
                    onClick={() => pickSession(s.session_id)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="line-clamp-2 text-body-sm text-ink/90">
                      {s.preview || `Phiên ${s.session_id.slice(0, 8)}`}
                    </div>
                    <div className="mt-1 text-caption text-ink/50">
                      {s.updated_at ? new Date(s.updated_at).toLocaleString("vi-VN") : s.session_id.slice(0, 8)}
                      {isCurrent && " · phiên hiện tại"}
                    </div>
                  </button>
                  <button
                    onClick={() => setConfirmSid(s.session_id)}
                    disabled={deleting === s.session_id}
                    aria-label="Xóa hội thoại"
                    title="Xóa hội thoại"
                    className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-ink/35 opacity-0 transition hover:bg-error/10 hover:text-error focus:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-error/30 disabled:opacity-40 group-hover:opacity-100"
                  >
                    {deleting === s.session_id ? (
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink/20 border-t-error" />
                    ) : (
                      <TrashIcon className="h-4 w-4" />
                    )}
                  </button>
                </div>
              );
            })
          )
        )}

        {!loading && tab === "alerts" && (
          alerts.length === 0 ? (
            <p className="py-6 text-center text-body-sm text-ink/40">Chưa có thông báo nào.</p>
          ) : (
            alerts.map((a) => (
              <button
                key={a._id}
                onClick={() => {
                  onPickAlert(a);
                  onAfterPick?.();
                }}
                className="w-full rounded-[12px] border border-ink/10 bg-white/50 p-3 text-left transition hover:bg-feature-cream/50"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-body-sm font-medium text-ink/90">
                    Cụm #{a.cluster_id} · {a.department}
                  </span>
                  {a.severity_snapshot != null && (
                    <span className="shrink-0 rounded bg-error px-1.5 py-0.5 text-caption font-semibold text-white">
                      sev {a.severity_snapshot}
                    </span>
                  )}
                </div>
                <div className="mt-1 text-caption text-ink/50">
                  {a.created_at ? new Date(a.created_at).toLocaleString("vi-VN") : ""}
                  {a.email?.status === "sent" && ` · đã gửi ${a.email.to ?? ""}`}
                </div>
              </button>
            ))
          )
        )}
      </div>

      {/* Modal xác nhận xóa — card cream Clay, nút error. Overlay nằm trong instance
          sidebar đang hiển thị (instance ẩn có display:none → không lộ). */}
      {confirmSid && (
        <div
          className="absolute inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div
            className="absolute inset-0 bg-ink/25"
            onClick={() => setConfirmSid(null)}
          />
          <div className="relative w-full max-w-xs rounded-card border border-ink/10 bg-canvas p-5 shadow-lg">
            <div className="flex items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-error/10 text-error">
                <TrashIcon className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <h3 className="text-title-md text-ink">Xóa hội thoại?</h3>
                <p className="mt-1 text-body-sm text-ink/60">
                  Toàn bộ tin nhắn của phiên này sẽ bị xóa vĩnh viễn và không thể khôi phục.
                </p>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setConfirmSid(null)}
                className="rounded-xl border border-ink/15 px-4 py-2 text-button text-ink/70 transition hover:bg-white/60"
              >
                Hủy
              </button>
              <button
                onClick={confirmDelete}
                className="rounded-xl bg-error px-4 py-2 text-button text-white transition hover:bg-error/90"
              >
                Xóa
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast phản hồi — pill nổi đáy sidebar, tự ẩn. */}
      {toast && (
        <div className="pointer-events-none absolute inset-x-0 bottom-4 z-50 flex justify-center px-4">
          <div
            className={`flex items-center gap-2 rounded-full px-4 py-2 text-body-sm font-medium shadow-lg ${
              toast.kind === "success" ? "bg-ink text-white" : "bg-error text-white"
            }`}
          >
            <span
              className={`grid h-4 w-4 place-items-center rounded-full text-[10px] font-semibold ${
                toast.kind === "success" ? "bg-success text-ink" : "bg-white/25 text-white"
              }`}
            >
              {toast.kind === "success" ? "✓" : "!"}
            </span>
            {toast.text}
          </div>
        </div>
      )}
    </div>
  );
}
