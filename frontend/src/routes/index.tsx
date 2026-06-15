/**
 * index.tsx — SheetAgent main page
 *
 * Backend endpoints used:
 *   POST /api/upload/              — attach file
 *   POST /api/chat/                — send message
 *   GET  /api/download/excel/:fn   — download .xlsx
 *   WS   /ws/:session_id           — live log stream
 *
 * Human-in-the-loop:
 *   • Clarify option buttons → sends __choice:<key> to backend
 *   • Stop button → AbortController cancels in-flight request
 */
import { useMemo, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { ChatPanel } from "@/components/sheet-agent/ChatPanel";
import { WelcomeScreen } from "@/components/sheet-agent/WelcomeScreen";
import { SheetView } from "@/components/sheet-agent/SheetView";
import { ChartView } from "@/components/sheet-agent/ChartView";
import { LeftSidebar } from "@/components/sheet-agent/LeftSidebar";
import {
  sendMessage,
  uploadFile,
  downloadExcel,
  abortCurrentRequest,
  connectWebSocket,
  disconnectWebSocket,
  actionToMessageFields,
  detectPastedTable,
  type AgentFile,
  type ChartData,
  type ChatMessage,
  type ChatSession,
  type ClarifyOption,
  type SheetData,
} from "@/lib/sheet-agent";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sheet Agent — AI spreadsheets & charts" },
      {
        name: "description",
        content:
          "Paste data or describe a sheet. Sheet Agent builds tables, charts, and dashboards instantly.",
      },
    ],
  }),
  component: SheetAgentPage,
});

let idc = 0;
const uid = () => `${Date.now()}-${++idc}`;

function SheetAgentPage() {
  const [messages,     setMessages]     = useState<ChatMessage[]>([]);
  const [status,       setStatus]       = useState<"idle" | "loading">("idle");
  const [sheet,        setSheet]        = useState<SheetData | null>(null);
  const [charts,       setCharts]       = useState<ChartData[]>([]);
  const [files,        setFiles]        = useState<AgentFile[]>([]);
  const [recentChats,  setRecentChats]  = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [activeFileId, setActiveFileId] = useState<string | undefined>();
  const [sidebarOpen,  setSidebarOpen]  = useState(true);

  const sessionIdRef    = useRef<string | null>(null);
  const uploadedPathRef = useRef<string | null>(null);
  const seenFilenames   = useRef<Set<string>>(new Set());

  function chatTitle(msgs: ChatMessage[]) {
    const firstUser = msgs.find((m) => m.role === "user");
    const raw = firstUser?.text?.trim() || "New conversation";
    return raw.length > 50 ? `${raw.slice(0, 50)}…` : raw;
  }

  function persistCurrentChat() {
    if (messages.length === 0) return;
    const id = activeChatId ?? uid();
    const session: ChatSession = {
      id,
      title: chatTitle(messages),
      messages: [...messages],
      files: [...files],
      sheet,
      charts: [...charts],
      createdAt: new Date().toISOString(),
      sessionId: sessionIdRef.current,
    };
    setRecentChats((prev) => [session, ...prev.filter((c) => c.id !== id)].slice(0, 20));
    if (!activeChatId) setActiveChatId(id);
  }

  function resetActiveChat() {
    disconnectWebSocket();
    sessionIdRef.current    = null;
    uploadedPathRef.current = null;
    seenFilenames.current.clear();
    setMessages([]);
    setSheet(null);
    setCharts([]);
    setFiles([]);
    setActiveFileId(undefined);
    setActiveChatId(null);
    setStatus("idle");
  }

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleNewChat = () => {
    abortCurrentRequest();
    persistCurrentChat();
    resetActiveChat();
  };

  const handleSelectChat = (chatId: string) => {
    if (chatId === activeChatId) return;
    abortCurrentRequest();
    const target = recentChats.find((c) => c.id === chatId);
    if (!target) return;
    persistCurrentChat();
    resetActiveChat();
    setActiveChatId(target.id);
    setMessages(target.messages);
    setFiles(target.files);
    setSheet(target.sheet);
    setCharts(target.charts);
    sessionIdRef.current = target.sessionId ?? null;
    if (target.sessionId) setupWs(target.sessionId);
  };

  const showWelcome = messages.length === 0;

  // ── WebSocket ─────────────────────────────────────────────────────────────
  function setupWs(sessionId: string) {
    connectWebSocket(sessionId, (event) => {
      const { type, data } = event as { type: string; data: Record<string, unknown> };
      if (type === "excel_ready") {
        const filename = String(data.filename ?? "");
        const title    = String(data.title    ?? "Excel file");
        if (!filename || seenFilenames.current.has(filename)) return;
        seenFilenames.current.add(filename);
        addMsg({ role: "assistant", text: `✅ **${title}** is ready!`,
                 trigger: "download", filename, fileTitle: title });
      }
    });
  }

  function addMsg(msg: Omit<ChatMessage, "id">) {
    setMessages((p) => [...p, { id: uid(), ...msg }]);
  }

  function applyPayload(s?: SheetData, ch?: ChartData[], af?: AgentFile[]) {
    if (s) {
      setSheet(s);
      const f: AgentFile = { id: uid(), name: s.title ?? "Generated sheet",
                              kind: "sheet", createdAt: new Date().toISOString() };
      setFiles((p) => [f, ...p]);
      setActiveFileId(f.id);
    }
    if (ch?.length) {
      setCharts(ch);
      setFiles((p) => [...ch.map((c) => ({ id: c.id, name: c.title,
        kind: "chart" as const, createdAt: new Date().toISOString() })), ...p]);
    }
    if (af?.length) setFiles((p) => [...af, ...p]);
  }

  // ── Core backend call ─────────────────────────────────────────────────────
  async function callBackend(text: string) {
    setStatus("loading");
    try {
      const res = await sendMessage(text, sessionIdRef.current, uploadedPathRef.current);

      if (res.session_id && res.session_id !== sessionIdRef.current) {
        sessionIdRef.current = res.session_id;
        setupWs(res.session_id);
      }
      uploadedPathRef.current = null;

      const extra = actionToMessageFields(res.action);

      if (extra.trigger === "download" && extra.filename &&
          seenFilenames.current.has(extra.filename)) {
        addMsg({ role: "assistant", text: res.text });
      } else {
        if (extra.trigger === "download" && extra.filename)
          seenFilenames.current.add(extra.filename);
        addMsg({ role: "assistant", text: res.text, ...extra });
      }

    } catch (err: unknown) {
      const e = err as { name?: string; message?: string };
      if (e?.name === "AbortError") return; // user stopped — message already added

      // Graceful local fallback when backend is unreachable
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      const localSheet = lastUser ? detectPastedTable(lastUser.text) : null;
      if (localSheet) {
        addMsg({
          role: "assistant",
          text: `I found **${localSheet.rows.length} rows** with columns: ${localSheet.columns.join(", ")}.\nWhat would you like me to build?`,
          trigger: "clarify",
          options: [
            { id: "basic",          label: "📋 Basic Sheet"          },
            { id: "with_chart",     label: "📊 + Bar Chart"          },
            { id: "with_dashboard", label: "📈 + Dashboard"          },
            { id: "full",           label: "🎯 Full (Recommended)", recommended: true },
          ],
        });
      } else {
        addMsg({ role: "assistant", text: `❌ ${e?.message ?? "Could not reach backend"}.` });
        toast.error("Backend not reachable — is the server running?");
      }
    } finally {
      setStatus("idle");
    }
  }

  // ── Public handlers (passed to ChatPanel) ─────────────────────────────────
  const handleSend = (text: string) => {
    if (!activeChatId) setActiveChatId(uid());
    addMsg({ role: "user", text });
    callBackend(text);
  };

  const handleStop = () => {
    abortCurrentRequest();
    setStatus("idle");
    addMsg({ role: "assistant", text: "⏹ Stopped. Send a new message whenever you're ready." });
  };

  const handleUpload = async (file: File) => {
    toast.info(`Uploading ${file.name}…`);
    try {
      const res = await uploadFile(file);
      sessionIdRef.current    = res.session_id;
      uploadedPathRef.current = res.file_path;
      setupWs(res.session_id);
      toast.success(`${file.name} ready — tell me what to do with it`);
      return res;
    } catch (err: unknown) {
      const e = err as { message?: string };
      toast.error(`Upload failed: ${e?.message ?? "unknown error"}`);
      throw err;
    }
  };

  const handleDownload = async (filename: string) => {
    try {
      const blob = await downloadExcel(filename);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const e = err as { message?: string };
      toast.error(`Download failed: ${e?.message ?? "unknown error"}`);
    }
  };

  const handlePickOption = async (opt: ClarifyOption) => {
    addMsg({ role: "user", text: opt.label });
    try {
      const res = await sendMessage(`__choice:${opt.id}`, sessionIdRef.current, null);
      const extra = actionToMessageFields(res.action);
      addMsg({ role: "assistant", text: res.text, ...extra });
    } catch {
      // Local demo fallback
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      const localSheet = lastUser ? detectPastedTable(lastUser.text) : null;
      if (!localSheet) {
        addMsg({ role: "assistant", text: "Paste your data first, then pick an option." });
        return;
      }
      setStatus("loading");
      applyPayload(localSheet);
      const numCol = localSheet.columns.find((c, i) =>
        localSheet.rows.every((r) => typeof r[i] === "number"));
      const xCol = localSheet.columns[0];
      const localCharts: ChartData[] = [];
      if (opt.id !== "basic" && numCol) {
        const data = localSheet.rows.map((r) => {
          const o: Record<string, string | number> = {};
          localSheet.columns.forEach((c, i) => (o[c] = r[i]));
          return o;
        });
        localCharts.push({ id: uid(), type: "bar",
          title: `${numCol} by ${xCol}`, data, xKey: xCol, yKeys: [numCol] });
        if (opt.id === "with_dashboard" || opt.id === "full")
          localCharts.push({ id: uid(), type: "line",
            title: `Trend — ${numCol}`, data, xKey: xCol, yKeys: [numCol] });
      }
      if (localCharts.length) applyPayload(undefined, localCharts);
      addMsg({ role: "assistant",
        text: `Done! Built **${opt.label}** with ${localSheet.rows.length} rows${localCharts.length ? ` and ${localCharts.length} chart(s)` : ""}.` });
      setStatus("idle");
    }
  };

  const hasArtifacts = useMemo(() => sheet !== null || charts.length > 0, [sheet, charts]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Toaster richColors position="top-center" />

      <LeftSidebar
        files={files}
        recentChats={recentChats}
        activeChatId={activeChatId}
        activeId={activeFileId}
        onSelect={setActiveFileId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((o) => !o)}
      />

      <section className={hasArtifacts
        ? "flex w-[440px] flex-col border-r border-border"
        : "flex flex-1 flex-col"}>
        <ChatPanel
          messages={messages} status={status}
          onSend={handleSend} onStop={handleStop}
          onUpload={handleUpload} onDownload={handleDownload}
          onPickOption={handlePickOption}
          showWelcome={showWelcome}
          welcomeSlot={<WelcomeScreen onPick={handleSend} />}
        />
      </section>

      {hasArtifacts && (
        <section className="flex-1 overflow-y-auto bg-muted/20 p-6">
          <div className="mx-auto max-w-5xl space-y-6">
            {sheet && <SheetView sheet={sheet} />}
            {charts.map((c) => <ChartView key={c.id} chart={c} />)}
          </div>
        </section>
      )}
    </div>
  );
}
