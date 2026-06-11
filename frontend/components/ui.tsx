"use client";

import React from "react";

export function Card({
  title,
  right,
  className = "",
  children,
}: {
  title?: string;
  right?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-card border border-ink/10 bg-white/60 p-4 ${className}`}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h3 className="text-sm font-semibold text-ink/80">{title}</h3>}
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function EmptyState({ message = "Chưa có dữ liệu enrich" }: { message?: string }) {
  return (
    <div className="flex h-[260px] flex-col items-center justify-center text-center text-ink/40">
      <span className="text-3xl">∅</span>
      <p className="mt-2 text-sm">{message}</p>
    </div>
  );
}

export function Loading() {
  return (
    <div className="flex h-[260px] items-center justify-center text-sm text-ink/40">Đang tải…</div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="flex h-[260px] items-center justify-center px-4 text-center text-sm text-error">
      Lỗi: {message}
    </div>
  );
}

// Bọc trạng thái loading/error/empty quanh nội dung chart.
export function StatefulChart<T>({
  loading,
  error,
  data,
  isEmpty,
  children,
}: {
  loading: boolean;
  error: string | null;
  data: T | null;
  isEmpty: (d: T) => boolean;
  children: (d: T) => React.ReactNode;
}) {
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  if (!data || isEmpty(data)) return <EmptyState />;
  return <>{children(data)}</>;
}
