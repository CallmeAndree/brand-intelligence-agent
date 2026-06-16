"use client";

import { useState } from "react";
import Markdown from "./Markdown";
import type { MonitorArtifact } from "@/lib/types";

const TYPE_LABEL: Record<string, string> = {
  narrative: "Report",
  root_cause: "Nguyên nhân gốc",
  response_strategy: "Chiến lược phản hồi",
  brand_voice: "Brand voice",
  seeding_comments: "Seeding",
};

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-feature-ochre/20 text-ink/70",
  approved: "bg-feature-teal/15 text-feature-teal",
  discarded: "bg-ink/10 text-ink/40",
};

export default function ArtifactCard({
  artifact,
  onApprove,
  onDiscard,
  onRegenerate,
  onSendToChat,
  busy,
}: {
  artifact: MonitorArtifact;
  onApprove: () => void;
  onDiscard: () => void;
  onRegenerate: () => void;
  onSendToChat: () => void;
  busy?: boolean;
}) {
  const variants = artifact.variants ?? null;
  const [activeVariant, setActiveVariant] = useState(0);
  const [copied, setCopied] = useState(false);
  const isDraft = artifact.status === "draft";

  // nội dung đang hiển thị (variant đang chọn hoặc content_md) → dùng cho nút copy
  const visibleContent =
    variants && variants.length > 0
      ? variants[activeVariant]?.content_md ?? ""
      : artifact.content_md;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(visibleContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard có thể bị chặn (context không secure) — bỏ qua im lặng
    }
  };

  return (
    <div className="rounded-card border border-ink/10 bg-white/70 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-title-sm text-ink/90">
            {TYPE_LABEL[artifact.type] ?? artifact.type}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-caption font-medium ${
              STATUS_STYLE[artifact.status] ?? ""
            }`}
          >
            {artifact.status}
          </span>
        </div>
        {artifact.created_at && (
          <span className="text-caption text-ink/40">
            {artifact.created_at.slice(0, 16).replace("T", " ")}
          </span>
        )}
      </div>

      {/* Thanh hành động — đặt ở ĐẦU card (trên nội dung) để thao tác nhanh không phải cuộn xuống. */}
      <div className="mb-3 flex flex-wrap gap-2 border-b border-ink/5 pb-3 text-button">
        {isDraft && (
          <>
            <button
              onClick={onApprove}
              disabled={busy}
              className="rounded-[10px] bg-feature-teal px-3 py-1 text-white disabled:opacity-40"
            >
              Approve
            </button>
            <button
              onClick={onDiscard}
              disabled={busy}
              className="rounded-[10px] border border-ink/15 px-3 py-1 text-ink/70 disabled:opacity-40"
            >
              Reject
            </button>
          </>
        )}
        <button
          onClick={handleCopy}
          className={`flex items-center gap-1 rounded-[10px] border px-3 py-1 transition ${
            copied
              ? "border-feature-teal/40 text-feature-teal"
              : "border-ink/15 text-ink/70 hover:bg-ink/5"
          }`}
        >
          {copied ? (
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
          {copied ? "Đã copy" : "Copy"}
        </button>
        <button
          onClick={onRegenerate}
          disabled={busy}
          className="rounded-[10px] border border-ink/15 px-3 py-1 text-ink/70 disabled:opacity-40"
        >
          Regenerate
        </button>
        <button
          onClick={onSendToChat}
          disabled={busy}
          className="rounded-[10px] border border-feature-blue/40 px-3 py-1 text-feature-blue disabled:opacity-40"
        >
          ➡ Gửi sang Chat
        </button>
      </div>

      {variants && variants.length > 0 ? (
        <>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {variants.map((v, i) => (
              <button
                key={i}
                onClick={() => setActiveVariant(i)}
                className={`rounded-full px-2.5 py-1 text-caption transition ${
                  i === activeVariant
                    ? "bg-feature-lavender/40 font-medium text-ink"
                    : "bg-ink/5 text-ink/60 hover:bg-ink/10"
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>
          <Markdown>{variants[activeVariant]?.content_md ?? ""}</Markdown>
        </>
      ) : (
        <Markdown>{artifact.content_md}</Markdown>
      )}
    </div>
  );
}
