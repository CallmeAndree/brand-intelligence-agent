"use client";

import type {
  Alert,
  ApiEnvelope,
  ArtifactType,
  ClusterDetail,
  MonitorArtifact,
} from "./types";

async function unwrap<T>(res: Response): Promise<T> {
  const json = (await res.json()) as ApiEnvelope<T>;
  if (!res.ok || !json.success || json.data === undefined) {
    throw new Error(json.message || `Lỗi ${res.status}`);
  }
  return json.data;
}

export async function fetchClusterDetail(
  clusterId: string,
  skip = 0,
  limit = 20,
): Promise<ClusterDetail> {
  const res = await fetch(`/api/clusters/${clusterId}?skip=${skip}&limit=${limit}`);
  return unwrap<ClusterDetail>(res);
}

export async function fetchArtifacts(clusterId: string): Promise<MonitorArtifact[]> {
  const res = await fetch(`/api/clusters/${clusterId}/artifacts`);
  return unwrap<MonitorArtifact[]>(res);
}

export async function generateArtifact(
  clusterId: string,
  type: ArtifactType,
): Promise<MonitorArtifact> {
  const res = await fetch(`/api/clusters/${clusterId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type }),
  });
  return unwrap<MonitorArtifact>(res);
}

// Sinh artifact dạng SSE: gọi onDelta cho mỗi chunk text, trả MonitorArtifact
// cuối cùng (đã có _id, đã lưu draft phía Runtime 1). Tự parse khung SSE.
export async function generateArtifactStream(
  clusterId: string,
  type: ArtifactType,
  onDelta: (text: string) => void,
): Promise<MonitorArtifact> {
  const res = await fetch(`/api/clusters/${clusterId}/generate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type }),
  });
  if (!res.ok || !res.body) throw new Error(`Lỗi ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let final: MonitorArtifact | null = null;
  let errMsg: string | null = null;

  const handle = (event: string, data: string) => {
    if (!data) return;
    if (event === "delta") onDelta((JSON.parse(data) as { text: string }).text);
    else if (event === "done") final = (JSON.parse(data) as { artifact: MonitorArtifact }).artifact;
    else if (event === "error") errMsg = (JSON.parse(data) as { message: string }).message;
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      let event = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      handle(event, dataLines.join("\n"));
    }
  }

  if (errMsg) throw new Error(errMsg);
  if (!final) throw new Error("Stream kết thúc nhưng không nhận được artifact");
  return final;
}

export async function artifactAction(
  artifactId: string,
  action: "approve" | "discard",
): Promise<void> {
  const res = await fetch(`/api/artifacts/${artifactId}/${action}`, {
    method: "POST",
  });
  await unwrap<unknown>(res);
}

export async function sendManualAlert(clusterId: string): Promise<Alert> {
  const res = await fetch(`/api/alerts/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cluster_id: Number(clusterId) }),
  });
  return unwrap<Alert>(res);
}
