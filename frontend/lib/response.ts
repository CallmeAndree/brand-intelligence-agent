import { NextResponse } from "next/server";
import type { ApiEnvelope } from "./types";

// Envelope { success, data, message } — giống StandardResponse của backend.
export function ok<T>(data: T): NextResponse<ApiEnvelope<T>> {
  return NextResponse.json({ success: true, data });
}

export function fail(message: string, status = 500): NextResponse<ApiEnvelope<never>> {
  return NextResponse.json({ success: false, message }, { status });
}

// Bọc handler để bắt lỗi → trả message (không lộ stack), không crash server.
export async function handle<T>(
  fn: () => Promise<T>
): Promise<NextResponse<ApiEnvelope<T>>> {
  try {
    const data = await fn();
    return ok(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Lỗi truy vấn dữ liệu";
    console.error("[api]", err);
    return fail(message, 500);
  }
}
