/**
 * sheet-agent.ts  — Backend API client for SheetAgent
 *
 * Matches backend/app/api/routes/{chat,upload,download,ws}.py exactly.
 *
 *   POST /api/chat/                    — { message, session_id, uploaded_file_path }
 *                                       → { text, intent, action, session_id }
 *   GET  /api/chat/history             — fetch user's private chat sessions (requires auth)
 *   POST /api/upload/                  — multipart file
 *                                       → { session_id, file_name, file_type, file_path, message }
 *   GET  /api/download/excel/:filename — streams .xlsx
 *   WS   /ws/:session_id               — live log + excel_ready events
 */
import { API_BASE, buildApiUrl, buildWebSocketUrl } from "./runtime-config";

export { API_BASE };

// ── Types ─────────────────────────────────────────────────────────────────────

export type ChatRole = "user" | "assistant";

export interface ClarifyOption {
  id: string;
  label: string;
  icon?: string;
  recommended?: boolean;
}

export interface SheetData {
  columns: string[];
  rows: (string | number)[][];
  title?: string;
}

export interface ChartData {
  id: string;
  type: "bar" | "line" | "pie" | "area";
  title: string;
  data: Record<string, string | number>[];
  xKey: string;
  yKeys: string[];
}

export interface AgentFile {
  id: string;
  name: string;
  kind: "sheet" | "chart" | "doc";
  createdAt: string;
}

export interface ChatSession {
  id: string;
  title: string;
  message_count: string;
  created_at: string;
  updated_at: string;
}

export interface ChatAction {
  trigger?: "download" | "clarify" | "quota_exceeded" | "approve_all" | "run_pipeline";
  filename?: string;
  title?: string;
  download_url?: string;
  waiting_for?: string;
  options?: ClarifyOption[];
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  trigger?: "clarify" | "download" | "quota_exceeded";
  options?: ClarifyOption[];
  sheet?: SheetData;
  charts?: ChartData[];
  files?: AgentFile[];
  filename?: string;
  fileTitle?: string;
  /** File name shown as a chip in the user's message bubble */
  attachedFileName?: string;
}

interface BackendChatResponse {
  text: string;
  intent: string;
  action: ChatAction;
  session_id?: string;
}

interface UploadResponse {
  session_id: string;
  file_name: string;
  file_type: string;
  file_path: string;
  message: string;
}

// ── Abort controller for Stop button ───────────────────────────────────────────

let _currentAbort: AbortController | null = null;

export function abortCurrentRequest() {
  _currentAbort?.abort();
  _currentAbort = null;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function sendMessage(
  message: string,
  sessionId?: string | null,
  uploadedFilePath?: string | null,
): Promise<BackendChatResponse> {
  _currentAbort = new AbortController();
  
  // Import auth helpers to get token
  const { getToken } = await import('./auth');
  const token = getToken();
  
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  const res = await fetch(buildApiUrl("/api/chat/"), {
    method: "POST",
    headers,
    signal: _currentAbort.signal,
    body: JSON.stringify({
      message,
      session_id: sessionId ?? null,
      uploaded_file_path: uploadedFilePath ?? null,
    }),
  });
  _currentAbort = null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `Server error ${res.status}`);
  }
  return res.json();
}

// ── Chat History (Secure) ─────────────────────────────────────────────────────

export async function fetchChatHistory(token?: string): Promise<ChatSession[]> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  const res = await fetch(buildApiUrl("/api/chat/history"), {
    method: "GET",
    headers,
  });
  
  if (!res.ok) {
    if (res.status === 401) {
      return [];
    }
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `Failed to fetch history: ${res.status}`);
  }
  
  return res.json() as Promise<ChatSession[]>;
}

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  action: ChatAction;
  created_at: string;
}

export async function fetchChatMessages(
  sessionId: string,
  token?: string,
): Promise<StoredMessage[]> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(buildApiUrl(`/api/chat/history/${sessionId}`), {
    method: "GET",
    headers,
  });

  if (!res.ok) {
    if (res.status === 401) return [];
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `Failed to fetch messages: ${res.status}`);
  }
  return res.json() as Promise<StoredMessage[]>;
}

export async function deleteChatSession(
  sessionId: string,
  token?: string,
): Promise<void> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(buildApiUrl(`/api/chat/history/${sessionId}`), {
    method: "DELETE",
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `Delete failed: ${res.status}`);
  }
}

// ── File upload ───────────────────────────────────────────────────────────────

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(buildApiUrl("/api/upload/"), {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

// ── Excel download ────────────────────────────────────────────────────────────

export async function downloadExcel(filename: string): Promise<Blob> {
  const res = await fetch(buildApiUrl(`/api/download/excel/${filename}`));
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  return res.blob();
}

// ── WebSocket live logs ───────────────────────────────────────────────────────

export type LogLevel = "info" | "warning" | "error" | "success";

export interface LogEntry {
  timestamp: string;
  agent: string;
  message: string;
  level: LogLevel;
}

type WsCallback = (event: { type: string; data: unknown }) => void;
let _wsSocket: WebSocket | null = null;
let _wsCallback: WsCallback | null = null;

export function connectWebSocket(sessionId: string, onEvent: WsCallback) {
  if (_wsSocket) {
    _wsSocket.close();
    _wsSocket = null;
  }
  _wsCallback = onEvent;
  const ws = new WebSocket(buildWebSocketUrl(`/ws/${sessionId}`));

  ws.onmessage = (e) => {
    if (e.data === "pong") return;
    try {
      const payload = JSON.parse(e.data);
      _wsCallback?.(payload);
    } catch {
      // ignore malformed frames
    }
  };
  ws.onclose = () => { _wsSocket = null; };
  _wsSocket = ws;
  return ws;
}

export function disconnectWebSocket() {
  _wsSocket?.close();
  _wsSocket = null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

export function actionToMessageFields(action: ChatAction): Partial<ChatMessage> {
  if (!action?.trigger) return {};

  if (action.trigger === "download" && action.filename) {
    return { trigger: "download", filename: action.filename, fileTitle: action.title };
  }
  if (action.trigger === "clarify" && action.options?.length) {
    return { trigger: "clarify", options: action.options };
  }
  if (action.trigger === "quota_exceeded") {
    return { trigger: "quota_exceeded" };
  }
  return {};
}

// Client-side pasted-table detector (offline/demo fallback only)
export function detectPastedTable(input: string): SheetData | null {
  const lines = input
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length < 3) return null;
  const split = (l: string) =>
    l.split(/\t|,|\s{2,}|\s\|\s|\s-\s/).map((c) => c.trim()).filter(Boolean);
  const rows  = lines.map(split);
  const width = rows[0].length;
  if (width < 2 || !rows.every((r) => r.length === width)) return null;
  const hasHeader = rows[0].every((c) => isNaN(Number(c)));
  const columns   = hasHeader ? rows[0] : rows[0].map((_, i) => `Column ${i + 1}`);
  const body      = (hasHeader ? rows.slice(1) : rows).map((r) =>
    r.map((c) => (isNaN(Number(c)) ? c : Number(c))),
  );
  return { columns, rows: body };
}
