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
  { type: "narrative", label: "Narrative", tip: "Tóm tắt diễn biến cụm", color: "bg-feature-pink/15 text-feature-pink" },
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
    queueContextInject({ content_md: art.content_md, cluster_id: art.cluster_id });
    router.push("/chat");
  };

  if (!clusterId) {
    return (
      <Card title="Workspace cụm">
        <div className="flex h-[240px] items-center justify-center text-center text-sm text-ink/40">
          Chọn một cụm critical bên trái để xem chi tiết và sinh nội dung.
        </div>
      </Card>
    );
  }

  const band = bandOf(detail?.severity_max ?? null);

  return (
    <Card
      title={detail?.label ?? "Đang tải cụm…"}
      right={
        detail?.severity_max != null && (
          <span
            className="rounded px-2 py-0.5 text-xs font-semibold text-white"
            style={{ backgroundColor: band ? bandColor(band) : "#c9c2b0" }}
          >
            sev {detail.severity_max}
          </span>
        )
      }
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-ink/50">
          {detail ? `${detail.count.toLocaleString("vi-VN")} mention` : ""}
        </span>
        <button
          onClick={onAlert}
          disabled={alerting}
          className="rounded-[10px] bg-error px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {alerting ? "Đang gửi…" : "⚠ Alert ngay"}
        </button>
      </div>

      {/* GenerationToolbar */}
      <div className="mb-4 flex flex-wrap gap-2">
        {TOOLS.map((t) => (
          <button
            key={t.type}
            title={t.tip}
            onClick={() => onGenerate(t.type)}
            disabled={busyType !== null}
            className={`rounded-[10px] px-3 py-1.5 text-sm font-medium transition disabled:opacity-40 ${t.color}`}
          >
            {busyType === t.type ? "Đang sinh…" : `+ ${t.label}`}
          </button>
        ))}
      </div>

      {toast && (
        <div
          className={`mb-3 rounded-[10px] px-3 py-2 text-sm ${
            toast.kind === "ok"
              ? "bg-feature-teal/15 text-feature-teal"
              : "bg-error/10 text-error"
          }`}
        >
          {toast.text}
        </div>
      )}

      {/* Card preview realtime trong khi stream */}
      {streaming && (
        <div className="mb-3 rounded-card border border-feature-pink/30 bg-white/70 p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-sm font-semibold text-ink/90">
              {TOOLS.find((t) => t.type === streaming.type)?.label ?? streaming.type}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-feature-pink/15 px-2 py-0.5 text-xs font-medium text-feature-pink">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-feature-pink" />
              Đang sinh…
            </span>
          </div>
          {streaming.text ? (
            <Markdown>{streaming.text}</Markdown>
          ) : (
            <p className="text-sm text-ink/40">Đang kết nối tới AI…</p>
          )}
        </div>
      )}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} />
      ) : artifacts.length === 0 && !streaming ? (
        <div className="py-8 text-center text-sm text-ink/40">
          Chưa có artifact. Bấm một công cụ phía trên để AI sinh nội dung.
        </div>
      ) : (
        <div className="space-y-3">
          {artifacts.map((art) => (
            <ArtifactCard
              key={art._id}
              artifact={art}
              busy={busyId === art._id}
              onApprove={() => onAction(art, "approve")}
              onDiscard={() => onAction(art, "discard")}
              onRegenerate={() => onGenerate(art.type)}
              onSendToChat={() => onSendToChat(art)}
            />
          ))}
        </div>
      )}
    </Card>
  );
}
