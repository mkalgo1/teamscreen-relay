export interface WorkerInfo {
  workerId: string;
  name: string;
  department: string;
  hostname: string;
  status: "online" | "streaming" | "idle";
  screenResolution: string;
  lastPing: number;
  streamRequested?: boolean;
  guidanceMessage?: string;
  ip?: string;
}

export interface StreamFrame {
  workerId: string;
  frame: string; // Base64 JPEG
  timestamp: number;
}

// Global in-memory storage across API routes on warm serverless instances
interface GlobalRelayStore {
  workers: Map<string, WorkerInfo>;
  frames: Map<string, StreamFrame>;
}

declare global {
  // eslint-disable-next-line no-var
  var __relayStore: GlobalRelayStore | undefined;
}

if (!global.__relayStore) {
  global.__relayStore = {
    workers: new Map<string, WorkerInfo>(),
    frames: new Map<string, StreamFrame>(),
  };
}

const store = global.__relayStore;

export function updateWorkerPing(data: {
  workerId: string;
  name?: string;
  department?: string;
  hostname?: string;
  status?: "online" | "streaming" | "idle";
  screenResolution?: string;
  ip?: string;
}): WorkerInfo {
  const existing = store.workers.get(data.workerId);
  const now = Date.now();

  const updated: WorkerInfo = {
    workerId: data.workerId,
    name: data.name || existing?.name || "Worker Node",
    department: data.department || existing?.department || "Operations",
    hostname: data.hostname || existing?.hostname || "Workstation",
    status: data.status || existing?.status || "online",
    screenResolution: data.screenResolution || existing?.screenResolution || "1920x1080",
    lastPing: now,
    streamRequested: existing?.streamRequested ?? false,
    guidanceMessage: existing?.guidanceMessage ?? "",
    ip: data.ip || existing?.ip || "",
  };

  store.workers.set(data.workerId, updated);
  return updated;
}

export function getActiveWorkers(timeoutMs = 12000): WorkerInfo[] {
  const now = Date.now();
  const list: WorkerInfo[] = [];

  for (const [id, worker] of store.workers.entries()) {
    if (now - worker.lastPing <= timeoutMs) {
      list.push(worker);
    } else {
      // Auto-prune dead workers after 30s
      if (now - worker.lastPing > 30000) {
        store.workers.delete(id);
        store.frames.delete(id);
      }
    }
  }

  return list.sort((a, b) => b.lastPing - a.lastPing);
}

export function setStreamSession(
  workerId: string,
  streamRequested?: boolean,
  guidanceMessage?: string
): WorkerInfo | null {
  const worker = store.workers.get(workerId);
  if (!worker) return null;

  if (typeof streamRequested === "boolean") {
    worker.streamRequested = streamRequested;
    if (!streamRequested) {
      worker.status = "online";
    } else {
      worker.status = "streaming";
    }
  }

  if (typeof guidanceMessage === "string") {
    worker.guidanceMessage = guidanceMessage;
  }

  store.workers.set(workerId, worker);
  return worker;
}

export function setFrame(workerId: string, frameBase64: string): void {
  store.frames.set(workerId, {
    workerId,
    frame: frameBase64,
    timestamp: Date.now(),
  });
}

export function getFrame(workerId: string): StreamFrame | null {
  return store.frames.get(workerId) || null;
}
