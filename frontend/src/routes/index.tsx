/**
 * index.tsx — SheetAgent main page with auth gate + smart greeting
 *
 * Auth flow:
 *  1. Check localStorage for saved token + user
 *  2. If not logged in → show <AuthPage />
 *  3. If logged in → show the full SheetAgent app
 *  4. Header shows user name + logout button
 *
 * Greeting: "Good morning/afternoon/evening, {first_name}" — updates to
 * actual time of day, not hardcoded.
 */
import { useMemo, useRef, useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { ChatPanel } from "@/components/sheet-agent/ChatPanel";
import { WelcomeScreen } from "@/components/sheet-agent/WelcomeScreen";
import { SheetView } from "@/components/sheet-agent/SheetView";
import { ChartView } from "@/components/sheet-agent/ChartView";
import { LeftSidebar } from "@/components/sheet-agent/LeftSidebar";
import { AuthPage } from "@/components/sheet-agent/AuthPage";
import {
  isLoggedIn, getSavedUser, logout as authLogout,
  getMe, type User,
} from "@/lib/auth";
import {
  sendMessage, uploadFile, downloadExcel,
  abortCurrentRequest, connectWebSocket, disconnectWebSocket,
  actionToMessageFields, detectPastedTable,
  type AgentFile, type ChartData, type ChatMessage,
  type ClarifyOption, type SheetData,
} from "@/lib/sheet-agent";
import { LogOut, User as UserIcon } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SheetAgent AI — Smart Excel Builder" },
      { name: "description", content: "AI-powered Excel sheets, charts, and dashboards." },
    ],
  }),
  component: SheetAgentPage,
});

let idc = 0;
const uid = () => `${Date.now()}-${++idc}`;

function SheetAgentPage() {
  // ── Auth state ─────────────────────────────────────────────────────────────
  // IMPORTANT (SSR safety): initial state must be IDENTICAL on the server and
  // on the client's first render, or React throws a hydration mismatch.
  // We always start with user=null, authChecking=true — the same on both —
  // then resolve the real auth state inside useEffect, which only ever runs
  // in the browser (never during SSR).
  const [user,         setUser]         = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  // Resolve real auth state — client only, runs once after mount
  useEffect(() => {
    if (!isLoggedIn()) { setAuthChecking(false); return; }

    // Show the cached user immediately for a snappy UI, then verify in
    // the background in case the token has expired.
    const cached = getSavedUser();
    if (cached) setUser(cached);

    getMe()
      .then((u) => { setUser(u); })
      .catch(() => {
        // Token invalid/expired → log out silently
        authLogout();
        setUser(null);
      })
      .finally(() => setAuthChecking(false));
  }, []);

  // ── App state ──────────────────────────────────────────────────────────────
  const [messages,     setMessages]     = useState<ChatMessage[]>([]);
  const [status,       setStatus]       = useState<"idle" | "loading">("idle");
  const [sheet,        setSheet]        = useState<SheetData | null>(null);
  const [charts,       setCharts]       = useState<ChartData[]>([]);
  const [files,        setFiles]        = useState<AgentFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | undefined>();
  const [sidebarOpen,  setSidebarOpen]  = useState(true);

  const sessionIdRef    = useRef<string | null>(null);
  const uploadedPathRef = useRef<string | null>(null);
  const seenFilenames   = useRef<Set<string>>(new Set());

  // ── Smart greeting (updates live) ─────────────────────────────────────────
  const [greeting, setGreeting] = useState(() => getGreeting());
  useEffect(() => {
    const id = setInterval(() => setGreeting(getGreeting()), 60_000);
    return () => clearInterval(id);
  }, []);

  function getGreeting() {
    const h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  }

  // ── Auth handlers ──────────────────────────────────────────────────────────
  const handleAuth = (u: User) => setUser(u);

  const handleLogout = async () => {
    await authLogout();
    setUser(null);
    handleNewChat();
  };

  // ── Chat helpers ───────────────────────────────────────────────────────────
  const handleNewChat = () => {
    disconnectWebSocket();
    sessionIdRef.current    = null;
    uploadedPathRef.current = null;
    seenFilenames.current.clear();
    setMessages([]);
    setSheet(null);
    setCharts([]);
    setFiles([]);
    setActiveFileId(undefined);
  };

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
      setFiles((p) => [...ch.map((c) => ({
        id: c.id, name: c.title, kind: "chart" as const,
        createdAt: new Date().toISOString(),
      })), ...p]);
    }
    if (af?.length) setFiles((p) => [...af, ...p]);
  }

  // ── Backend call ───────────────────────────────────────────────────────────
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
      if (e?.name === "AbortError") return;
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      const localSheet = lastUser ? detectPastedTable(lastUser.text) : null;
      if (localSheet) {
        addMsg({
          role: "assistant",
          text: `I found **${localSheet.rows.length} rows**.\nWhat would you like me to build?`,
          trigger: "clarify",
          options: [
            { id: "basic",          label: "📋 Basic Sheet"                        },
            { id: "with_chart",     label: "📊 + Bar Chart"                        },
            { id: "with_dashboard", label: "📈 + Dashboard"                        },
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

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleSend = (text: string) => {
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
      addMsg({ role: "assistant", text: "Backend not reachable. Paste your data and try again." });
    }
  };

  const hasArtifacts = useMemo(() => sheet !== null || charts.length > 0, [sheet, charts]);

  // ── Render gates ───────────────────────────────────────────────────────────

  // Loading token verification
  if (authChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm">Signing you in…</span>
        </div>
      </div>
    );
  }

  // Not logged in → auth page
  if (!user) {
    return (
      <>
        <Toaster richColors position="top-center" />
        <AuthPage onAuth={handleAuth} />
      </>
    );
  }

  // First name for greeting
  const firstName = user.full_name?.split(" ")[0] ?? "there";
  const showWelcome = messages.length === 0;

  // ── Main app ───────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <Toaster richColors position="top-center" />

      {/* Top header bar */}
      <header className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-card/80 px-4 backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">SheetAgent AI</span>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            — {greeting}, {firstName}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <UserIcon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{user.email}</span>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        <LeftSidebar
          files={files} activeId={activeFileId} onSelect={setActiveFileId}
          onNewChat={handleNewChat} open={sidebarOpen}
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
            welcomeSlot={
              <WelcomeScreen
                onPick={handleSend}
                greeting={greeting}
                userName={firstName}
              />
            }
          />
        </section>

        {hasArtifacts && (
          <section className="flex-1 overflow-y-auto bg-muted/20 p-6">
            <div className="mx-auto max-w-5xl space-y-6">
              {sheet  && <SheetView  sheet={sheet} />}
              {charts.map((c) => <ChartView key={c.id} chart={c} />)}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
