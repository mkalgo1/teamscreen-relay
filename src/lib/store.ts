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

export interface InputEvent {
  id: string;
  workerId: string;
  eventType: "click" | "type" | "key";
  xRatio?: number;
  yRatio?: number;
  text?: string;
  key?: string;
  timestamp: number;
}

export interface FileItem {
  name: string;
  isDir: boolean;
  size: number;
  modified: number;
}

export interface FileCommand {
  id: string;
  workerId: string;
  action: "list" | "upload" | "download" | "launch" | "delete" | "mkdir" | "autostart";
  path?: string;
  fileName?: string;
  fileData?: string; // Base64
  timestamp: number;
}

export interface FileResult {
  workerId: string;
  action?: string;
  currentPath: string;
  items?: FileItem[];
  fileName?: string;
  fileData?: string; // Base64 for downloaded files
  statusMessage?: string;
  success?: boolean;
  timestamp: number;
}

// Global in-memory storage across API routes on warm serverless instances
interface GlobalRelayStore {
  workers: Map<string, WorkerInfo>;
  frames: Map<string, StreamFrame>;
  inputs: Map<string, InputEvent[]>;
  fileCommands: Map<string, FileCommand[]>;
  fileResults: Map<string, FileResult>;
}

declare global {
  // eslint-disable-next-line no-var
  var __relayStore: GlobalRelayStore | undefined;
}

if (!global.__relayStore) {
  global.__relayStore = {
    workers: new Map<string, WorkerInfo>(),
    frames: new Map<string, StreamFrame>(),
    inputs: new Map<string, InputEvent[]>(),
    fileCommands: new Map<string, FileCommand[]>(),
    fileResults: new Map<string, FileResult>(),
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
      if (now - worker.lastPing > 30000) {
        store.workers.delete(id);
        store.frames.delete(id);
        store.inputs.delete(id);
        store.fileCommands.delete(id);
        store.fileResults.delete(id);
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

export function queueInputEvent(event: Omit<InputEvent, "id" | "timestamp">): InputEvent {
  const inputEvent: InputEvent = {
    ...event,
    id: `inp_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    timestamp: Date.now(),
  };

  const queue = store.inputs.get(event.workerId) || [];
  queue.push(inputEvent);
  if (queue.length > 50) queue.shift();
  store.inputs.set(event.workerId, queue);

  return inputEvent;
}

export function popInputEvents(workerId: string): InputEvent[] {
  const queue = store.inputs.get(workerId) || [];
  if (queue.length === 0) return [];

  store.inputs.set(workerId, []);
  return queue;
}

export function queueFileCommand(cmd: Omit<FileCommand, "id" | "timestamp">): FileCommand {
  const fileCmd: FileCommand = {
    ...cmd,
    id: `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    timestamp: Date.now(),
  };

  const queue = store.fileCommands.get(cmd.workerId) || [];
  queue.push(fileCmd);
  if (queue.length > 20) queue.shift();
  store.fileCommands.set(cmd.workerId, queue);

  return fileCmd;
}

export function popFileCommands(workerId: string): FileCommand[] {
  const queue = store.fileCommands.get(workerId) || [];
  if (queue.length === 0) return [];

  store.fileCommands.set(workerId, []);
  return queue;
}

export function setFileResult(result: FileResult): void {
  store.fileResults.set(result.workerId, result);
}

export function getFileResult(workerId: string): FileResult | null {
  return store.fileResults.get(workerId) || null;
}
