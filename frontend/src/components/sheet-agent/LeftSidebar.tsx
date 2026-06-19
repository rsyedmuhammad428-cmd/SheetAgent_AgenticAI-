/**
 * LeftSidebar.tsx — Fully responsive
 *
 * Mobile  (<768px): hidden by default, slides in as a full-height overlay
 *                   over the chat. A hamburger button in the header opens it.
 *                   Tapping the dark backdrop closes it.
 * Tablet  (≥768px): same overlay behaviour but wider (288px).
 * Desktop (≥1024px): fixed inline sidebar, never overlays.
 */
import { useEffect, useState } from "react";
import {
  FileSpreadsheet, BarChart3, FileText,
  PanelLeftClose, PanelLeft, Plus, Search,
  Moon, Sun, Sparkles, MessageSquare, MoreHorizontal, Trash2,
} from "lucide-react";
import type { AgentFile, ChatSession } from "@/lib/sheet-agent";
import { cn } from "@/lib/utils";

const ICONS = {
  sheet: FileSpreadsheet,
  chart: BarChart3,
  doc:   FileText,
} as const;

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "light";
    const stored = localStorage.getItem("theme");
    if (stored === "dark" || stored === "light") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

export function LeftSidebar({
  files, recentChats, activeChatId, activeId,
  onSelect, onSelectChat, onDeleteChat, onNewChat, open, onToggle,
}: {
  files: AgentFile[];
  recentChats: ChatSession[];
  activeChatId?: string | null;
  activeId?: string;
  onSelect?: (id: string) => void;
  onSelectChat?: (id: string) => void;
  onDeleteChat?: (id: string) => void;
  onNewChat: () => void;
  open: boolean;
  onToggle: () => void;
}) {
  const { theme, toggle } = useTheme();
  // Track which chat item's context menu is open (by id, null = none)
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  // Close menu when clicking anywhere outside
  useEffect(() => {
    if (!openMenuId) return;
    const close = () => setOpenMenuId(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [openMenuId]);

  // Close sidebar when pressing Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape" && open) onToggle(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onToggle]);

  return (
    <>
      {/* ── Mobile/Tablet overlay backdrop ───────────────────────────────── */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}

      {/* ── Sidebar panel ────────────────────────────────────────────────── */}
      <aside
        className={cn(
          // Base: fixed overlay on mobile, inline on desktop
          "fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-sidebar",
          "transition-transform duration-300 ease-in-out",
          // Desktop: inline (not fixed), never overlays
          "lg:relative lg:z-auto lg:translate-x-0 lg:transition-[width] lg:duration-300",
          // Width
          "w-72",
          // Mobile/tablet: slide in/out via transform
          open ? "translate-x-0" : "-translate-x-full",
          // Desktop: collapse via width instead
          "lg:w-72",
          !open && "lg:w-0",
        )}
      >
        <div
          className={cn(
            "flex h-full flex-col overflow-hidden transition-opacity duration-200",
            open ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold tracking-tight">Sheet Agent</span>
            </div>
            <button
              onClick={onToggle}
              aria-label="Close sidebar"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>

          {/* New chat */}
          <div className="px-3 pb-2">
            <button
              onClick={() => { onNewChat(); if (window.innerWidth < 1024) onToggle(); }}
              className="flex w-full items-center gap-2 rounded-lg border border-border bg-card px-3 py-2.5 text-sm font-medium transition hover:bg-accent active:scale-95"
            >
              <Plus className="h-4 w-4" />
              New chat
            </button>
          </div>

          {/* Search */}
          <div className="px-3 pb-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-2.5 py-2 text-xs text-muted-foreground">
              <Search className="h-3.5 w-3.5" />
              <span>Search workspace</span>
            </div>
          </div>

          {/* Section label */}
          <div className="mt-2 px-4 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Workspace
          </div>

          {/* Scrollable list */}
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
                      <li key={chat.id} className="relative">
                        {/* Row: chat button + 3-dot menu button */}
                        <div
                          className={cn(
                            "group flex w-full items-center rounded-lg text-xs transition",
                            activeChatId === chat.id
                              ? "bg-primary/10 text-primary"
                              : "hover:bg-accent",
                          )}
                        >
                          {/* Chat title — clicking selects the chat */}
                          <button
                            onClick={() => {
                              onSelectChat?.(chat.id);
                              setOpenMenuId(null);
                              if (window.innerWidth < 1024) onToggle();
                            }}
                            className="flex flex-1 min-w-0 items-center gap-2.5 px-2.5 py-2 text-left"
                          >
                            <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                            <span className="truncate">{chat.title}</span>
                          </button>

                          {/* 3-dot button — visible on hover or when menu open */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId((prev) => prev === chat.id ? null : chat.id);
                            }}
                            aria-label="Chat options"
                            className={cn(
                              "mr-1 shrink-0 rounded-md p-1 text-muted-foreground transition",
                              "opacity-0 group-hover:opacity-100",
                              openMenuId === chat.id && "opacity-100 bg-accent",
                            )}
                          >
                            <MoreHorizontal className="h-3.5 w-3.5" />
                          </button>
                        </div>

                        {/* Dropdown menu */}
                        {openMenuId === chat.id && (
                          <div
                            className="absolute right-1 top-8 z-50 min-w-[140px] rounded-lg border border-border bg-popover shadow-md"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              onClick={() => {
                                setOpenMenuId(null);
                                onDeleteChat?.(chat.id);
                              }}
                              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive hover:bg-destructive/10 transition-colors"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              Delete chat
                            </button>
                          </div>
                        )}
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
                            onClick={() => {
                              onSelect?.(f.id);
                              if (window.innerWidth < 1024) onToggle();
                            }}
                            className={cn(
                              "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition active:scale-95",
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

          {/* Theme toggle */}
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
      </aside>

      {/* ── Collapsed toggle button (desktop only, inline sidebar closed) ── */}
      {!open && (
        <button
          onClick={onToggle}
          aria-label="Open sidebar"
          className="hidden lg:flex absolute left-2 top-3 z-10 rounded-md border border-border bg-background p-1.5 text-muted-foreground shadow-sm transition hover:bg-accent hover:text-foreground"
        >
          <PanelLeft className="h-4 w-4" />
        </button>
      )}
    </>
  );
}
