export interface WorkerLocation {
  latitude: number;
  longitude: number;
  accuracy?: number;
  provider?: string;
  timestamp?: number;
}

export interface WorkerInfo {
  workerId: string;
  name: string;
  department: string;
  hostname: string;
  platform?: "windows" | "android" | string;
  deviceType?: "desktop" | "phone" | string;
  status: "online" | "streaming" | "idle";
  screenResolution: string;
  lastPing: number;
  streamRequested?: boolean;
  guidanceMessage?: string;
  guidanceNotepadActive?: boolean;
  workerMicActive?: boolean;
  ceoMicActive?: boolean;
  ip?: string;
  location?: WorkerLocation;
}

export interface AudioPacket {
  workerId: string;
  channel: "worker_to_ceo" | "ceo_to_worker";
  chunk: string; // Base64 PCM 16kHz
  seq: number;
  timestamp: number;
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

export interface CustomerLog {
  id: string;
  workerId: string;
  workerName: string;
  type: "call" | "message";
  customerName: string;
  customerPhone: string;
  direction: "incoming" | "outgoing";
  status: "completed" | "missed" | "followup";
  duration?: string;
  notes?: string;
  timestamp: number;
}

// Global in-memory storage across API routes on warm serverless instances
interface GlobalRelayStore {
  workers: Map<string, WorkerInfo>;
  frames: Map<string, StreamFrame>;
  inputs: Map<string, InputEvent[]>;
  fileCommands: Map<string, FileCommand[]>;
  fileResults: Map<string, FileResult>;
  customerLogs: CustomerLog[];
  audioPackets: Map<string, AudioPacket[]>;
  audioSeq: number;
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
    customerLogs: [],
    audioPackets: new Map<string, AudioPacket[]>(),
    audioSeq: 0,
  };
}

const store = global.__relayStore;

export function updateWorkerPing(data: {
  workerId: string;
  name?: string;
  department?: string;
  hostname?: string;
  platform?: string;
  deviceType?: string;
  status?: "online" | "streaming" | "idle";
  screenResolution?: string;
  ip?: string;
  location?: WorkerLocation;
}): WorkerInfo {
  const existing = store.workers.get(data.workerId);
  const now = Date.now();

  const isAndroid =
    data.platform === "android" ||
    data.deviceType === "phone" ||
    data.workerId.startsWith("android") ||
    (data.hostname && data.hostname.toLowerCase().includes("android")) ||
    (data.department && data.department.toLowerCase().includes("phone"));

  const platform = data.platform || (isAndroid ? "android" : "windows");
  const deviceType = data.deviceType || (isAndroid ? "phone" : "desktop");

  // De-duplicate: If an existing worker has the same hostname, evict the old entry immediately
  if (data.hostname && data.hostname.trim().length > 0) {
    const cleanHost = data.hostname.toLowerCase().trim();
    for (const [existingId, existingWorker] of store.workers.entries()) {
      if (
        existingId !== data.workerId &&
        existingWorker.hostname &&
        existingWorker.hostname.toLowerCase().trim() === cleanHost
      ) {
        store.workers.delete(existingId);
        store.frames.delete(existingId);
        store.inputs.delete(existingId);
        store.fileCommands.delete(existingId);
        store.fileResults.delete(existingId);
      }
    }
  }

  const updated: WorkerInfo = {
    workerId: data.workerId,
    name: data.name || existing?.name || "Worker Node",
    department: data.department || existing?.department || "Operations",
    hostname: data.hostname || existing?.hostname || "Workstation",
    platform,
    deviceType,
    status: data.status || existing?.status || "online",
    screenResolution: data.screenResolution || existing?.screenResolution || "1920x1080",
    lastPing: now,
    streamRequested: existing?.streamRequested ?? false,
    guidanceMessage: existing?.guidanceMessage ?? "",
    guidanceNotepadActive: existing?.guidanceNotepadActive ?? false,
    workerMicActive: existing?.workerMicActive ?? false,
    ceoMicActive: existing?.ceoMicActive ?? false,
    ip: data.ip || existing?.ip || "",
    location: data.location || existing?.location,
  };

  store.workers.set(data.workerId, updated);
  return updated;
}

export function getActiveWorkers(timeoutMs = 8000): WorkerInfo[] {
  const now = Date.now();
  const list: WorkerInfo[] = [];
  const seenDevices = new Set<string>();

  // Sort by newest ping first
  const allWorkers = Array.from(store.workers.values()).sort((a, b) => b.lastPing - a.lastPing);

  for (const worker of allWorkers) {
    if (now - worker.lastPing <= timeoutMs) {
      // De-duplicate by hostname or workerId so each physical device is listed exactly once
      const devKey = (worker.hostname || worker.workerId).toLowerCase().trim();
      if (!seenDevices.has(devKey)) {
        seenDevices.add(devKey);
        list.push(worker);
      }
    } else {
      if (now - worker.lastPing > 12000) {
        store.workers.delete(worker.workerId);
        store.frames.delete(worker.workerId);
        store.inputs.delete(worker.workerId);
        store.fileCommands.delete(worker.workerId);
        store.fileResults.delete(worker.workerId);
      }
    }
  }

  return list;
}

export function clearStaleWorkers(): number {
  const count = store.workers.size;
  store.workers.clear();
  store.frames.clear();
  store.inputs.clear();
  store.fileCommands.clear();
  store.fileResults.clear();
  store.audioPackets.clear();
  return count;
}

export function setStreamSession(
  workerId: string,
  streamRequested?: boolean,
  guidanceMessage?: string,
  guidanceNotepadActive?: boolean,
  workerMicActive?: boolean,
  ceoMicActive?: boolean
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

  if (typeof guidanceNotepadActive === "boolean") {
    worker.guidanceNotepadActive = guidanceNotepadActive;
  }

  if (typeof workerMicActive === "boolean") {
    worker.workerMicActive = workerMicActive;
  }

  if (typeof ceoMicActive === "boolean") {
    worker.ceoMicActive = ceoMicActive;
  }

  store.workers.set(workerId, worker);
  return worker;
}

export function pushAudioChunk(
  workerId: string,
  channel: "worker_to_ceo" | "ceo_to_worker",
  chunk: string
): AudioPacket {
  store.audioSeq = (store.audioSeq || 0) + 1;
  const packet: AudioPacket = {
    workerId,
    channel,
    chunk,
    seq: store.audioSeq,
    timestamp: Date.now(),
  };

  const key = `${workerId}:${channel}`;
  const queue = store.audioPackets.get(key) || [];
  queue.push(packet);
  // Keep last 30 packets in memory buffer (~6-8s of audio)
  if (queue.length > 30) queue.shift();
  store.audioPackets.set(key, queue);

  return packet;
}

export function getAudioChunks(
  workerId: string,
  channel: "worker_to_ceo" | "ceo_to_worker",
  afterSeq = 0
): AudioPacket[] {
  const key = `${workerId}:${channel}`;
  const queue = store.audioPackets.get(key) || [];
  if (afterSeq <= 0) return queue.slice(-3); // Return latest 3 chunks on fresh connect
  return queue.filter((p) => p.seq > afterSeq);
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

export function addCustomerLog(log: Omit<CustomerLog, "id" | "timestamp">): CustomerLog {
  const newLog: CustomerLog = {
    ...log,
    id: `log_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    timestamp: Date.now(),
  };

  store.customerLogs.unshift(newLog);
  // Keep last 500 logs
  if (store.customerLogs.length > 500) {
    store.customerLogs.length = 500;
  }

  return newLog;
}

export function getCustomerLogs(workerId?: string): CustomerLog[] {
  if (!workerId) {
    return store.customerLogs;
  }
  return store.customerLogs.filter((l) => l.workerId === workerId);
}
