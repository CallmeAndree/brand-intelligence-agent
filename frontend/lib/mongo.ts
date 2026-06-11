import { MongoClient, Collection, Document } from "mongodb";

// Mongo client singleton — tái dùng connection giữa các lần hot-reload trong dev.
// Chỉ dùng server-side (API routes, Node runtime). KHÔNG import vào client component.

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

export async function mentionsCollection(): Promise<Collection<Document>> {
  const db = await getDb();
  return db.collection("mentions");
}
