import { MongoClient } from "mongodb";
import { remoteCollection, remoteModeEnabled, type RemoteColl } from "./remoteCollection";

// Mongo client singleton — tái dùng connection giữa các lần hot-reload trong dev.
// Chỉ dùng server-side (API routes, Node runtime). KHÔNG import vào client component.
//
// Hai chế độ (giống Runtime 1 chọn theo REPO_MODE):
//  - local/VM: nối Mongo trực tiếp qua MONGODB_URI (driver mongodb).
//  - Vercel (DATA_BACKEND_URL set): KHÔNG nối Mongo (Mongo private trên VM) — đọc
//    qua data-backend HTTP facade qua Cloudflare quick tunnel (xem remoteCollection.ts).

const uri = process.env.MONGODB_URI;
const dbName = process.env.MONGO_DB || "brand_intel";

if (!uri) {
  // Không throw ở module-load (để build không vỡ); route sẽ báo lỗi rõ khi gọi.
  console.warn("[mongo] MONGODB_URI chưa được set trong .env.local");
}

declare global {
  // eslint-disable-next-line no-var
  var _mongoClientPromise: Promise<MongoClient> | undefined;
}

function getClientPromise(): Promise<MongoClient> {
  if (!uri) throw new Error("MONGODB_URI chưa cấu hình");
  if (!global._mongoClientPromise) {
    const client = new MongoClient(uri, { serverSelectionTimeoutMS: 5000 });
    global._mongoClientPromise = client.connect();
  }
  return global._mongoClientPromise;
}

export async function getDb() {
  const client = await getClientPromise();
  return client.db(dbName);
}

export async function collectionByName(name: string): Promise<RemoteColl> {
  if (remoteModeEnabled()) {
    return remoteCollection(name);
  }
  const db = await getDb();
  // Driver Collection thỏa cấu trúc RemoteColl cho subset method các route dùng.
  return db.collection(name) as unknown as RemoteColl;
}

export async function mentionsCollection(): Promise<RemoteColl> {
  return collectionByName("mentions");
}
