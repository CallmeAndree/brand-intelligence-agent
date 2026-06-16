"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, Loading, ErrorBox } from "./ui";
import ArtifactCard from "./ArtifactCard";
import Markdown from "./Markdown";
import { useFilters } from "@/lib/filters";
import { bandOf, bandColor } from "@/lib/severity";
import { queueContextInject } from "@/lib/chat";
import {
  artifactAction,
  fetchArtifacts,
  fetchClusterDetail,
  generateArtifactStream,
  sendManualAlert,
} from "@/lib/monitor";
import type {
  ArtifactType,
  ClusterDetail,
  MonitorArtifact,
} from "@/lib/types";

const TOOLS: { type: ArtifactType; label: string; tip: string; color: string }[] = [
  { type: "narrative", label: "Report", tip: "Tóm tắt diễn biến cụm", color: "bg-feature-blue/15 text-feature-blue" },
  { type: "root_cause", label: "Nguyên nhân", tip: "Phân tích nguyên nhân gốc", color: "bg-feature-teal/15 text-feature-teal" },
  { type: "response_strategy", label: "Chiến lược", tip: "Chiến lược phản hồi/xử lý", color: "bg-feature-lavender/30 text-ink" },
  { type: "brand_voice", label: "Brand voice", tip: "Nhiều phiên bản phản hồi theo tone", color: "bg-feature-peach/30 text-ink" },
  { type: "seeding_comments", label: "Seeding", tip: "Gợi ý bình luận seeding", color: "bg-feature-ochre/25 text-ink" },
];

type Toast = { kind: "ok" | "err"; text: string } | null;

export default function ClusterWorkspace() {
  const { filters } = useFilters();
  const router = useRouter();
  const clusterId = filters.clusterId;

  const [detail, setDetail] = useState<ClusterDetail | null>(null);
  const [artifacts, setArtifacts] = useState<MonitorArtifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyType, setBusyType] = useState<ArtifactType | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [alerting, setAlerting] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  // Artifact đang stream (hiển thị realtime trước khi lưu xong).
  const [streaming, setStreaming] = useState<{ type: ArtifactType; text: string } | null>(null);
  // Tab skill đang xem (mỗi skill 1 tab, không trộn list).
  const [activeTab, setActiveTab] = useState<ArtifactType>("narrative");

  const refresh = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const [d, a] = await Promise.all([
        fetchClusterDetail(id),
        fetchArtifacts(id),
      ]);
      setDetail(d);
      setArtifacts(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!clusterId) {
      setDetail(null);
      setArtifacts([]);
      return;
    }
    void refresh(clusterId);
  }, [clusterId, refresh]);

  const flash = (t: Toast) => {
    setToast(t);
    if (t) setTimeout(() => setToast(null), 4000);
  };

  const onGenerate = async (type: ArtifactType) => {
    if (!clusterId) return;
    setActiveTab(type);
    setBusyType(type);
    setStreaming({ type, text: "" });
    try {
      const art = await generateArtifactStream(clusterId, type, (delta) => {
        setStreaming((s) => (s ? { ...s, text: s.text + delta } : s));
      });
      setArtifacts((prev) => [art, ...prev]);
    } catch (e) {
      flash({ kind: "err", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setStreaming(null);
      setBusyType(null);
    }
  };

  const onAction = async (
    art: MonitorArtifact,
    action: "approve" | "discard",
  ) => {
    setBusyId(art._id);
    try {
      await artifactAction(art._id, action);
      if (action === "discard") {
        setArtifacts((prev) => prev.filter((x) => x._id !== art._id));
      } else {
        setArtifacts((prev) =>
          prev.map((x) => (x._id === art._id ? { ...x, status: "approved" } : x)),
        );
      }
    } catch (e) {
      flash({ kind: "err", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusyId(null);
    }
  };

  const onAlert = async () => {
    if (!clusterId) return;
    setAlerting(true);
    try {
      const alert = await sendManualAlert(clusterId);
      const s = alert.email?.status;
      flash({
        kind: s === "failed" ? "err" : "ok",
        text:
          s === "sent"
            ? `Đã gửi email alert tới ${alert.email.to} (${alert.department})`
            : s === "skipped"
              ? `Đã lưu alert (chưa cấu hình SMTP nên không gửi email) — ${alert.department}`
              : `Gửi email thất bại: ${alert.email.error ?? "lỗi"}`,
      });
    } catch (e) {
      flash({ kind: "err", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setAlerting(false);
    }
  };

  const onSendToChat = (art: MonitorArtifact) => {
    // Mang skill_type của artifact → Chat tự trang bị đúng skill Monitor để revise nội dung này.
    queueContextInject({
      content_md: art.content_md,
      cluster_id: art.cluster_id,
      skill_type: art.type,
    });
    router.push("/chat");
  };

  if (!clusterId) {
    return (
      <Card title="Workspace" scroll className="h-full">
        <div className="flex h-full min-h-[240px] items-center justify-center text-center text-body-sm text-ink/40">
          Chọn một cụm critical bên trái để xem chi tiết và sinh nội dung.
        </div>
      </Card>
    );
  }

  const band = bandOf(detail?.severity_max ?? null);

  return (
    <Card
      scroll
      className="h-full"
      title={detail?.label ?? "Đang tải cụm…"}
      right={
        detail?.severity_max != null && (
          <span
            className="rounded px-2 py-0.5 text-caption font-semibold text-white"
            style={{ backgroundColor: band ? bandColor(band) : "#c9c2b0" }}
          >
            sev {detail.severity_max}
          </span>
        )
      }
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-caption text-ink/50">
          {detail ? `${detail.count.toLocaleString("vi-VN")} mention` : ""}
        </span>
        <button
          onClick={onAlert}
          disabled={alerting}
          className="rounded-[10px] bg-error px-3 py-1.5 text-button text-white disabled:opacity-50"
        >
          {alerting ? "Đang gửi…" : "⚠ Alert ngay"}
        </button>
      </div>

      {/* TabBar 5 skill — pill bám category-tab/-active, badge đếm artifact theo type */}
      <div className="mb-4 flex flex-wrap gap-1.5 border-b border-ink/10 pb-3">
        {TOOLS.map((t) => {
          const count = artifacts.filter((a) => a.type === t.type).length;
          const isActive = activeTab === t.type;
          return (
            <button
              key={t.type}
              title={t.tip}
              onClick={() => setActiveTab(t.type)}
              className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-nav transition ${
                isActive
                  ? "bg-feature-cream text-ink"
                  : "bg-transparent text-ink/50 hover:text-ink/80"
              }`}
            >
              {t.label}
              {count > 0 && (
                <span
                  className={`rounded-full px-1.5 text-caption font-semibold ${
                    isActive ? "bg-ink/10 text-ink/70" : "bg-ink/5 text-ink/50"
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {toast && (
        <div
          className={`mb-3 rounded-[10px] px-3 py-2 text-body-sm ${
            toast.kind === "ok"
              ? "bg-feature-teal/15 text-feature-teal"
              : "bg-error/10 text-error"
          }`}
        >
          {toast.text}
        </div>
      )}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} />
      ) : (
        (() => {
          const tab = TOOLS.find((t) => t.type === activeTab)!;
          const tabArtifacts = artifacts.filter((a) => a.type === activeTab);
          const isStreamingTab = streaming?.type === activeTab;
          const busy = busyType === activeTab;
          return (
            <div className="space-y-3">
              {/* Nút sinh/sinh lại skill đang xem */}
              <button
                onClick={() => onGenerate(activeTab)}
                disabled={busyType !== null}
                className={`rounded-[10px] px-3 py-1.5 text-button transition disabled:opacity-40 ${tab.color}`}
              >
                {busy
                  ? "Đang sinh…"
                  : `${tabArtifacts.length > 0 ? "↻ Sinh lại" : "+ Sinh"} ${tab.label}`}
              </button>

              {/* Preview realtime khi đang stream skill này */}
              {isStreamingTab && (
                <div className="rounded-card border border-feature-blue/30 bg-white/70 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="text-title-sm text-ink/90">{tab.label}</span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-feature-blue/15 px-2 py-0.5 text-caption font-medium text-feature-blue">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-feature-blue" />
                      Đang sinh…
                    </span>
                  </div>
                  {streaming!.text ? (
                    <Markdown>{streaming!.text}</Markdown>
                  ) : (
                    <p className="text-body-sm text-ink/40">Đang kết nối tới AI…</p>
                  )}
                </div>
              )}

              {tabArtifacts.length === 0 && !isStreamingTab ? (
                <div className="py-8 text-center text-body-sm text-ink/40">
                  Chưa có nội dung “{tab.label}”. Bấm nút phía trên để AI sinh.
                </div>
              ) : (
                tabArtifacts.map((art) => (
                  <ArtifactCard
                    key={art._id}
                    artifact={art}
                    busy={busyId === art._id}
                    onApprove={() => onAction(art, "approve")}
                    onDiscard={() => onAction(art, "discard")}
                    onRegenerate={() => onGenerate(art.type)}
                    onSendToChat={() => onSendToChat(art)}
                  />
                ))
              )}
            </div>
          );
        })()
      )}
    </Card>
  );
}
