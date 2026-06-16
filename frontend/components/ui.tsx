"use client";

import React from "react";

export function Card({
  title,
  subtitle,
  right,
  className = "",
  scroll = false,
  bodyClassName = "",
  children,
}: {
  title?: string;
  // subtitle: dòng mô tả ngắn dưới title — giải thích biểu đồ đọc thế nào.
  subtitle?: string;
  right?: React.ReactNode;
  className?: string;
  // scroll: card thành flex-col + body cuộn riêng (min-h-0) — dùng cho layout viewport-bounded.
  scroll?: boolean;
  bodyClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-card border border-ink/10 bg-white/60 p-4 ${
        scroll ? "flex flex-col" : ""
      } ${className}`}
    >
      {(title || subtitle || right) && (
        <div className="mb-3 flex shrink-0 items-start justify-between gap-3">
          {(title || subtitle) && (
            <div className="min-w-0">
              {title && <h3 className="text-title-sm text-ink/80">{title}</h3>}
              {subtitle && <p className="mt-0.5 text-caption text-ink/40">{subtitle}</p>}
            </div>
          )}
          {right}
        </div>
      )}
      {scroll ? (
        <div className={`flex-1 overflow-y-auto min-h-0 ${bodyClassName}`}>{children}</div>
      ) : (
        children
      )}
    </div>
  );
}

export function EmptyState({ message = "Chưa có dữ liệu enrich" }: { message?: string }) {
  return (
    <div className="flex h-[260px] flex-col items-center justify-center text-center text-ink/40">
      <span className="text-3xl">∅</span>
      <p className="mt-2 text-body-sm">{message}</p>
    </div>
  );
}

export function Loading() {
  return (
    <div className="flex h-[260px] items-center justify-center text-body-sm text-ink/40">Đang tải…</div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="flex h-[260px] items-center justify-center px-4 text-center text-body-sm text-error">
      Lỗi: {message}
    </div>
  );
}

// Bọc trạng thái loading/error/empty quanh nội dung chart.
// Stale-while-revalidate: chỉ Loading/Error khi CHƯA có data; khi đã có data luôn render children,
// mờ opacity + nhãn "đang cập nhật…" lúc validating.
export function StatefulChart<T>({
  loading,
  validating = false,
  error,
  data,
  isEmpty,
  children,
}: {
  loading: boolean;
  validating?: boolean;
  error: string | null;
  data: T | null;
  isEmpty: (d: T) => boolean;
  children: (d: T) => React.ReactNode;
}) {
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox message={error} />;
  if (!data || isEmpty(data)) return <EmptyState />;
  return (
    <div className={`relative transition-opacity ${validating ? "opacity-60" : ""}`}>
      {validating && (
        <span className="pointer-events-none absolute right-1 top-1 z-10 rounded-full bg-ink/5 px-2 py-0.5 text-caption text-ink/50">
          đang cập nhật…
        </span>
      )}
      {children(data)}
    </div>
  );
}
