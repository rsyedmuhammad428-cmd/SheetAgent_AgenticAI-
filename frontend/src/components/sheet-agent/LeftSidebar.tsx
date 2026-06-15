import { useEffect, useState } from "react";
import {
  FileSpreadsheet,
  BarChart3,
  FileText,
  PanelLeftClose,
  PanelLeft,
  Plus,
  Search,
  Moon,
  Sun,
  Sparkles,
  MessageSquare,
} from "lucide-react";
import type { AgentFile, ChatSession } from "@/lib/sheet-agent";
import { cn } from "@/lib/utils";

const ICONS = {
  sheet: FileSpreadsheet,
  chart: BarChart3,
  doc: FileText,
} as const;

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "light";
    const stored = localStorage.getItem("theme");
    if (stored === "dark" || stored === "light") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

export function LeftSidebar({
  files,
  recentChats,
  activeChatId,
  activeId,
  onSelect,
  onSelectChat,
  onNewChat,
  open,
  onToggle,
}: {
  files: AgentFile[];
  recentChats: ChatSession[];
  activeChatId?: string | null;
  activeId?: string;
  onSelect?: (id: string) => void;
  onSelectChat?: (id: string) => void;
  onNewChat: () => void;
  open: boolean;
  onToggle: () => void;
}) {
  const { theme, toggle } = useTheme();

  return (
    <aside
      className={cn(
        "relative flex h-full flex-col border-r border-border bg-sidebar transition-[width] duration-300 ease-in-out",
        open ? "w-72" : "w-0",
      )}
    >
      <div
        className={cn(
          "flex h-full flex-col overflow-hidden transition-opacity duration-200",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold tracking-tight">Sheet Agent</span>
          </div>
          <button
            onClick={onToggle}
            aria-label="Collapse sidebar"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>

        <div className="px-3 pb-2">
          <button
            onClick={onNewChat}
            className="flex w-full items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium transition hover:bg-accent"
          >
            <Plus className="h-4 w-4" />
            New chat
          </button>
        </div>

        <div className="px-3 pb-2">
          <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-2.5 py-1.5 text-xs text-muted-foreground">
            <Search className="h-3.5 w-3.5" />
            <span>Search workspace</span>
          </div>
        </div>

        <div className="mt-2 px-4 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Workspace
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {recentChats.length === 0 && files.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
              Files and charts you create will appear here.
            </div>
          ) : (
            <ul className="space-y-0.5">
              {recentChats.length > 0 && (
                <>
                  <li className="px-2.5 pb-1 pt-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    Recent chats
                  </li>
                  {recentChats.map((chat) => (
                    <li key={chat.id}>
                      <button
                        onClick={() => onSelectChat?.(chat.id)}
                        className={cn(
                          "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-xs transition",
                          activeChatId === chat.id
                            ? "bg-primary/10 text-primary"
                            : "hover:bg-accent",
                        )}
                      >
                        <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{chat.title}</span>
                      </button>
                    </li>
                  ))}
                </>
              )}
              {files.length > 0 && (
                <>
                  {recentChats.length > 0 && (
                    <li className="px-2.5 pb-1 pt-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      Files
                    </li>
                  )}
                  {files.map((f) => {
                    const Icon = ICONS[f.kind];
                    return (
                      <li key={f.id}>
                        <button
                          onClick={() => onSelect?.(f.id)}
                          className={cn(
                            "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-xs transition",
                            activeId === f.id
                              ? "bg-primary/10 text-primary"
                              : "hover:bg-accent",
                          )}
                        >
                          <Icon className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{f.name}</span>
                        </button>
                      </li>
                    );
                  })}
                </>
              )}
            </ul>
          )}
        </div>

        <div className="border-t border-border p-2">
          <button
            onClick={toggle}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-muted-foreground transition hover:bg-accent hover:text-foreground"
          >
            {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </div>

      {!open && (
        <button
          onClick={onToggle}
          aria-label="Open sidebar"
          className="absolute left-2 top-3 z-10 rounded-md border border-border bg-background p-1.5 text-muted-foreground shadow-sm transition hover:bg-accent hover:text-foreground"
        >
          <PanelLeft className="h-4 w-4" />
        </button>
      )}
    </aside>
  );
}
