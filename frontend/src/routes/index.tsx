/**
 * index.tsx — SheetAgent main page — fully responsive
 *
 * Breakpoints:
 *  Mobile  <768px  : sidebar hidden, hamburger menu in header
 *  Tablet  768-1023px: sidebar as overlay, header compact
 *  Desktop ≥1024px : sidebar inline, full 3-column layout
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
import { getPakistanGreeting } from "@/lib/utils";
import {
  isLoggedIn, getSavedUser, logout as authLogout,
  getMe, getToken, type User,
} from "@/lib/auth";
import {
  sendMessage, uploadFile, downloadExcel, fetchChatHistory, fetchChatMessages, deleteChatSession,
  abortCurrentRequest, connectWebSocket, disconnectWebSocket,
  actionToMessageFields, detectPastedTable,
  type AgentFile, type ChartData, type ChatMessage, type ChatSession,
  type ClarifyOption, type SheetData,
} from "@/lib/sheet-agent";
import { LogOut, User as UserIcon, Menu } from "lucide-react";

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
  // ── Auth state (SSR-safe: always start null/true) ───────────────────────
  const [user,         setUser]         = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [recentChats,  setRecentChats]  = useState<ChatSession[]>([]);
  const [chatsLoading, setChatsLoading] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) { setAuthChecking(false); return; }
    const cached = getSavedUser();
    if (cached) setUser(cached);
    getMe()
      .then((u) => setUser(u))
      .catch(() => { authLogout(); setUser(null); })
      .finally(() => setAuthChecking(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    setChatsLoading(true);
    fetchChatHistory(getToken())
      .then(setRecentChats)
      .catch(() => setRecentChats([]))
      .finally(() => setChatsLoading(false));
  }, [user]);

  // ── App state ────────────────────────────────────────────────────────────
  const [messages,     setMessages]     = useState<ChatMessage[]>([]);
  const [status,       setStatus]       = useState<"idle" | "loading">("idle");
  const [sheet,        setSheet]        = useState<SheetData | null>(null);
  const [charts,       setCharts]       = useState<ChartData[]>([]);
  const [files,        setFiles]        = useState<AgentFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | undefined>();
  const [activeChatId, setActiveChatId] = useState<string | null>(null);

  // Sidebar: open by default on desktop, closed on mobile
  const [sidebarOpen, setSidebarOpen] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth >= 1024 : true
  );

  const sessionIdRef    = useRef<string | null>(null);
  const uploadedPathRef = useRef<string | null>(null);
  const seenFilenames   = useRef<Set<string>>(new Set());

  function resetConversationView() {
    disconnectWebSocket();
    sessionIdRef.current = null;
    uploadedPathRef.current = null;
    seenFilenames.current.clear();
    setMessages([]);
    setSheet(null);
    setCharts([]);
    setFiles([]);
    setActiveFileId(undefined);
  }

  // ── Pakistan-time greeting (updates every minute) ─────────────────────
  const [greeting, setGreeting] = useState("Good morning");
  useEffect(() => {
    setGreeting(getPakistanGreeting());
    const id = setInterval(() => setGreeting(getPakistanGreeting()), 60_000);
    return () => clearInterval(id);
  }, []);

  // ── Auth handlers ──────────────────────────────────────────────────────
  const handleAuth = (u: User) => setUser(u);

  const handleLogout = async () => {
    await authLogout();
    setUser(null);
    setRecentChats([]);
    handleNewChat();
  };

  // ── Chat helpers ────────────────────────────────────────────────────────
  const handleNewChat = () => {
    resetConversationView();
    setActiveChatId(null);
  };

  const handleSelectChat = async (chatId: string) => {
    resetConversationView();
    setActiveChatId(chatId);
    sessionIdRef.current = chatId;
    try {
      const stored = await fetchChatMessages(chatId, getToken() ?? undefined);
      setMessages(stored.map((m) => ({
        id: m.id,
        role: m.role,
        text: m.text,
        attachedFileName: typeof m.action?.attached_file_name === "string"
          ? m.action.attached_file_name
          : undefined,
        ...actionToMessageFields(m.action || {}),
      })));
      setupWs(chatId);
    } catch {
      toast.error("Could not load that conversation.");
    }
  };

  async function refreshChatHistory() {
    if (!user) return;
    try { setRecentChats(await fetchChatHistory(getToken())); } catch {}
  }

  const handleDeleteChat = async (chatId: string) => {
    try {
      await deleteChatSession(chatId, getToken() ?? undefined);
      // Remove from local state immediately (no reload needed)
      setRecentChats((prev) => prev.filter((c) => c.id !== chatId));
      // If the deleted chat was the active one, clear the view
      if (sessionIdRef.current === chatId) handleNewChat();
    } catch {
      toast.error("Could not delete that conversation.");
    }
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

  // ── Backend call ─────────────────────────────────────────────────────────
  async function callBackend(text: string, attachedFileName?: string) {
    setStatus("loading");
    try {
      const res = await sendMessage(
        text,
        sessionIdRef.current,
        uploadedPathRef.current,
        attachedFileName,
      );
      if (res.session_id && res.session_id !== sessionIdRef.current) {
        sessionIdRef.current = res.session_id;
        setActiveChatId(res.session_id);
        setupWs(res.session_id);
      } else if (res.session_id) {
        setActiveChatId(res.session_id);
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
      refreshChatHistory();
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
            { id: "basic",          label: "📋 Basic Sheet" },
            { id: "with_chart",     label: "📊 + Bar Chart" },
            { id: "with_dashboard", label: "📈 + Dashboard" },
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

  const handleSend = (text: string, attachedFileName?: string) => {
    addMsg({ role: "user", text, attachedFileName });
    callBackend(text, attachedFileName);
  };
  const handleStop = () => {
    abortCurrentRequest(); setStatus("idle");
    addMsg({ role: "assistant", text: "⏹ Stopped. Send a new message whenever you're ready." });
  };
  const handleUpload = async (file: File) => {
    toast.info(`Uploading ${file.name}…`);
    try {
      const res = await uploadFile(file);
      uploadedPathRef.current = res.file_path;
      toast.success(`${file.name} ready — tell me what to do with it`);
      return res;
    } catch (err: unknown) {
      toast.error(`Upload failed: ${(err as { message?: string })?.message ?? "unknown"}`);
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
      document.body.removeChild(a); URL.revokeObjectURL(url);
    } catch (err: unknown) {
      toast.error(`Download failed: ${(err as { message?: string })?.message ?? "unknown"}`);
    }
  };
  const handlePickOption = async (opt: ClarifyOption) => {
    addMsg({ role: "user", text: opt.label });
    try {
      const res  = await sendMessage(`__choice:${opt.id}`, sessionIdRef.current, null);
      const extra = actionToMessageFields(res.action);
      addMsg({ role: "assistant", text: res.text, ...extra });
    } catch {
      addMsg({ role: "assistant", text: "Backend not reachable. Paste your data and try again." });
    }
  };

  const hasArtifacts = useMemo(() => sheet !== null || charts.length > 0, [sheet, charts]);

  // ── Render gates ─────────────────────────────────────────────────────────
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

  if (!user) {
    return (
      <>
        <Toaster richColors position="top-center" />
        <AuthPage onAuth={handleAuth} />
      </>
    );
  }

  const firstName  = user.full_name?.split(" ")[0] ?? "there";
  const showWelcome = messages.length === 0;

  // ── Main app ──────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <Toaster richColors position="top-center" />

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card/80 px-3 backdrop-blur sm:px-4">
        <div className="flex items-center gap-2">
          {/* Hamburger — visible on mobile/tablet when sidebar closed */}
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            aria-label="Toggle sidebar"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>

          <span className="text-sm font-semibold text-foreground">SheetAgent AI</span>
          <span className="hidden text-xs text-muted-foreground md:inline">
            — {greeting}, {firstName}
          </span>
        </div>

        <div className="flex items-center gap-1 sm:gap-3">
          <div className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
            <UserIcon className="h-3.5 w-3.5" />
            <span className="hidden md:inline">{user.email}</span>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors sm:px-2.5"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────────────────── */}
      <div className="relative flex flex-1 overflow-hidden">

        {/* Sidebar */}
        <LeftSidebar
          files={files}
          recentChats={recentChats}
          activeId={activeFileId}
          activeChatId={activeChatId}
          onSelect={setActiveFileId}
          onSelectChat={handleSelectChat}
          onDeleteChat={handleDeleteChat}
          onNewChat={handleNewChat}
          open={sidebarOpen}
          onToggle={() => setSidebarOpen((o) => !o)}
        />

        {/* Chat panel — fills all remaining space */}
        <section className={cn(
          "flex min-w-0 flex-1 flex-col",
          // On desktop with artifacts: fixed width chat + artifact panel
          hasArtifacts && "lg:max-w-[480px]",
        )}>
          <ChatPanel
            key={activeChatId ?? "new-chat"}
            messages={messages}
            status={status}
            onSend={handleSend}
            onStop={handleStop}
            onUpload={handleUpload}
            onDownload={handleDownload}
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

        {/* Artifacts panel — only shows on ≥1024px when there's content */}
        {hasArtifacts && (
          <section className="hidden flex-1 overflow-y-auto bg-muted/20 p-4 lg:block lg:p-6">
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

// ── tiny cn helper so we can use cn() inline above without extra import ──
function cn(...classes: (string | false | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
