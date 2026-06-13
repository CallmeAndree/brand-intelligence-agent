import { EJSON } from "bson";
import type { Document } from "mongodb";

// Remote-mode DB access: thay vì nối Mongo trực tiếp (chỉ chạy được khi front-end
// ở cùng mạng VM), front-end deploy trên Vercel gọi data-backend qua Cloudflare
// quick tunnel — GIỐNG cách Runtime 1 dùng REPO_MODE=http. data-backend chạy cạnh
// Mongo, expose /repo/aggregate|find|count (xem data_backend/main.py).
//
// Body & response dùng Extended JSON (bson EJSON) để giữ kiểu Date/ObjectId/int
// qua HTTP — JSON thường biến Date thành string, làm hỏng $match range thời gian.

const RAW_BASE = process.env.DATA_BACKEND_URL;

export function remoteModeEnabled(): boolean {
  return !!RAW_BASE;
}

function base(): string {
  if (!RAW_BASE) throw new Error("DATA_BACKEND_URL chưa cấu hình");
  return RAW_BASE.replace(/\/$/, "");
}

async function call(path: string, spec: unknown): Promise<string> {
  const res = await fetch(`${base()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Data-Token": process.env.DATA_BACKEND_TOKEN || "",
    },
    body: EJSON.stringify(spec as Document) as unknown as string,
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`data-backend ${path} ${res.status}: ${detail.slice(0, 200)}`);
  }
  return res.text();
}

function parseDocs(text: string): Document[] {
  return EJSON.parse(text) as unknown as Document[];
}

// Cursor tối giản — đủ cho subset API mà các route đang dùng.
interface AggCursor {
  toArray(): Promise<Document[]>;
}
interface FindCursor {
  sort(s: Document): FindCursor;
  skip(n: number): FindCursor;
  limit(n: number): FindCursor;
  toArray(): Promise<Document[]>;
}
export interface RemoteColl {
  aggregate(pipeline: Document[]): AggCursor;
  find(filter: Document, opts?: { projection?: Document }): FindCursor;
  countDocuments(filter: Document): Promise<number>;
}

export function remoteCollection(collection: string): RemoteColl {
  return {
    aggregate(pipeline: Document[]): AggCursor {
      return {
        async toArray() {
          return parseDocs(await call("/repo/aggregate", { collection, pipeline }));
        },
      };
    },
    find(filter: Document, opts?: { projection?: Document }): FindCursor {
      const spec: Document = { collection, filter };
      if (opts?.projection) spec.projection = opts.projection;
      const cursor: FindCursor = {
        sort(s: Document) {
          spec.sort = s;
          return cursor;
        },
        skip(n: number) {
          spec.skip = n;
          return cursor;
        },
        limit(n: number) {
          spec.limit = n;
          return cursor;
        },
        async toArray() {
          return parseDocs(await call("/repo/find", spec));
        },
      };
      return cursor;
    },
    async countDocuments(filter: Document): Promise<number> {
      const text = await call("/repo/count", { collection, filter });
      return (JSON.parse(text) as { count: number }).count;
    },
  };
}
