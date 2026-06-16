"use client";

import { useCallback, useEffect, useState } from "react";

// Ghim cụm chủ đề muốn theo dõi — lưu THUẦN localStorage (persist theo trình duyệt,
// không cần backend). Khoá theo cluster_id (batch re-cluster có thể đổi id khi reseed —
// chấp nhận cho demo: id ổn định trong một phiên dữ liệu).
const STORAGE_KEY = "bi_pinned_clusters";

function read(): number[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "number") : [];
  } catch {
    return [];
  }
}

function write(ids: number[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    /* localStorage không khả dụng (private mode…) → bỏ qua, state vẫn chạy trong phiên */
  }
}

// Hook quản lý tập cụm đã ghim. Khởi tạo rỗng (tránh hydration mismatch SSR) rồi nạp
// từ localStorage ở effect mount. Đồng bộ giữa nhiều tab qua sự kiện `storage`.
export function usePinnedClusters() {
  const [pinned, setPinned] = useState<number[]>([]);

  useEffect(() => {
    setPinned(read());
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setPinned(read());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggle = useCallback((id: number) => {
    setPinned((prev) => {
      const next = prev.includes(id)
        ? prev.filter((x) => x !== id)
        : [...prev, id];
      write(next);
      return next;
    });
  }, []);

  const isPinned = useCallback((id: number) => pinned.includes(id), [pinned]);

  return { pinned, toggle, isPinned };
}
