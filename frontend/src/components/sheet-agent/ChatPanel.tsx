/**
 * ChatPanel.tsx — fully wired to backend
 *
 * New props vs original:
 *   onStop     — called when user clicks the red Stop button
 *   onUpload   — called when user attaches a file; returns UploadResponse
 *   onDownload — called when user clicks Download on a message card
 *
 * New features:
 *   • File attachment (📎 button + drag-and-drop)
 *   • Stop button (red ⏹) while agent is working
 *   • Download card rendered for trigger==="download" messages
 *   • Clarify option buttons for trigger==="clarify" (human-in-the-loop)
 *   • Awaiting-choice indicator when waiting for user selection
 */
import { useEffect, useRef, useState } from "react";
import {
  Send, Loader2, Sparkles, Paperclip, X,
  Square, Download, FileSpreadsheet, CheckCheck,
} from "lucide-react";
import type { ChatMessage, ClarifyOption } from "@/lib/sheet-agent";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface UploadResult {
  session_id: string;
  file_name: string;
  file_type: string;
  file_path: string;
  message: string;
}

interface ChatPanelProps {
  messages: ChatMessage[];
  status: "idle" | "loading";
  onSend: (text: string) => void;
  onStop: () => void;
  onUpload: (file: File) => Promise<UploadResult>;
  onDownload: (filename: string) => Promise<void>;
  onPickOption: (opt: ClarifyOption) => void;
  showWelcome: boolean;
  welcomeSlot?: React.ReactNode;
}

// ── File chip shown above input ───────────────────────────────────────────────
function FileChip({ name, uploading, done, onRemove }: {
  name: string; uploading: boolean; done: boolean; onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-muted px-2.5 py-1.5 text-xs max-w-[220px]">
      {uploading
        ? <Loader2 className="h-3 w-3 animate-spin shrink-0 text-primary" />
        : <span className="shrink-0">📎</span>
      }
      <span className="truncate flex-1 text-foreground">{name}</span>
      {done && <CheckCheck className="h-3 w-3 shrink-0 text-green-500" />}
      {!uploading && (
        <button onClick={onRemove} className="shrink-0 text-muted-foreground hover:text-foreground">
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

// ── Download card ─────────────────────────────────────────────────────────────
function DownloadCard({ filename, title, onDownload }: {
  filename: string; title?: string; onDownload: (f: string) => Promise<void>;
}) {
  const [st, setSt] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function handle() {
    setSt("loading");
    try {
      await onDownload(filename);
      setSt("done");
      setTimeout(() => setSt("idle"), 4000);
    } catch {
      setSt("error");
      setTimeout(() => setSt("idle"), 3000);
    }
  }

  const colors = {
    idle:    "bg-green-600 hover:bg-green-500",
    loading: "bg-green-700 opacity-60",
    done:    "bg-emerald-700",
    error:   "bg-red-700 hover:bg-red-600",
  };
  const labels = {
    idle: "Download Excel", loading: "Downloading…",
    done: "Downloaded ✓",  error:   "Retry",
  };

  return (
    <div className="mt-2 flex items-center gap-3 rounded-xl border border-green-700/40 bg-green-900/20 p-3">
      <FileSpreadsheet className="h-5 w-5 shrink-0 text-green-400" />
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-semibold text-green-300">{title ?? filename}</p>
        <p className="truncate text-[11px] text-green-600">{filename}</p>
      </div>
      <button
        onClick={handle}
        disabled={st === "loading"}
        className={cn(
          "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold text-white transition-all",
          colors[st],
        )}
      >
        {st === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> :
         st === "done"    ? <CheckCheck className="h-3.5 w-3.5" /> :
                            <Download className="h-3.5 w-3.5" />}
        {labels[st]}
      </button>
    </div>
  );
}

// ── Clarify option buttons ────────────────────────────────────────────────────
function ClarifyButtons({ options, onPick, disabled }: {
  options: ClarifyOption[];
  onPick: (opt: ClarifyOption) => void;
  disabled: boolean;
}) {
  const colorMap: Record<string, string> = {
    basic:          "border-border bg-background hover:border-primary/40 hover:bg-accent",
    with_chart:     "border-blue-500/40 bg-blue-900/20 text-blue-300 hover:bg-blue-800/40",
    with_dashboard: "border-purple-500/40 bg-purple-900/20 text-purple-300 hover:bg-purple-800/40",
    with_analysis:  "border-purple-500/40 bg-purple-900/20 text-purple-300 hover:bg-purple-800/40",
    full:           "border-primary bg-primary/10 text-primary hover:bg-primary/20 font-semibold",
  };

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt.id}
          onClick={() => onPick(opt)}
          disabled={disabled}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs transition disabled:opacity-40 disabled:cursor-not-allowed",
            colorMap[opt.id] ?? "border-border bg-background hover:bg-accent",
          )}
        >
          {opt.icon && <span className="mr-1">{opt.icon}</span>}
          {opt.label}
          {opt.recommended && <span className="ml-1.5 text-[10px] opacity-70">★</span>}
        </button>
      ))}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────
function MessageBubble({ message, onPickOption, onDownload, choicesDisabled }: {
  message: ChatMessage;
  onPickOption: (opt: ClarifyOption) => void;
  onDownload: (filename: string) => Promise<void>;
  choicesDisabled: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex w-full animate-fade-in", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("flex max-w-[85%] gap-3", isUser && "flex-row-reverse")}>
        {!isUser && (
          <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-fuchsia-500 text-white">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
        )}
        <div>
          <div className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
          )}>
            {/* Render **bold** markdown */}
            <div className="whitespace-pre-wrap">
              {message.text.split(/\*\*(.*?)\*\*/g).map((part, i) =>
                i % 2 === 1
                  ? <strong key={i} className="font-semibold">{part}</strong>
                  : part
              )}
            </div>

            {/* Clarify option buttons */}
            {message.trigger === "clarify" && message.options && (
              <ClarifyButtons
                options={message.options}
                onPick={onPickOption}
                disabled={choicesDisabled}
              />
            )}
          </div>

          {/* Download card (outside the bubble for visual separation) */}
          {message.trigger === "download" && message.filename && (
            <DownloadCard
              filename={message.filename}
              title={message.fileTitle}
              onDownload={onDownload}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main ChatPanel ─────────────────────────────────────────────────────────────
export function ChatPanel({
  messages, status, onSend, onStop, onUpload, onDownload,
  onPickOption, showWelcome, welcomeSlot,
}: ChatPanelProps) {
  const [input,        setInput]        = useState("");
  const [stagedFile,   setStagedFile]   = useState<File | null>(null);
  const [uploading,    setUploading]    = useState(false);
  const [uploadDone,   setUploadDone]   = useState(false);
  const [awaitChoice,  setAwaitChoice]  = useState(false);

  const taRef     = useRef<HTMLTextAreaElement>(null);
  const fileRef   = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, status]);

  useEffect(() => { taRef.current?.focus(); }, []);

  // Detect when agent sends a clarify message → show awaiting indicator
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && last?.trigger === "clarify") {
      setAwaitChoice(true);
    } else {
      setAwaitChoice(false);
    }
  }, [messages]);

  // ── File attach ──────────────────────────────────────────────────────────────
  async function handleFileAttach(file: File) {
    setStagedFile(file);
    setUploading(true);
    setUploadDone(false);
    try {
      await onUpload(file);
      setUploadDone(true);
      taRef.current?.focus();
    } catch {
      setStagedFile(null);
    } finally {
      setUploading(false);
    }
  }

  function onFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleFileAttach(f);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) handleFileAttach(f);
  }

  // ── Submit ───────────────────────────────────────────────────────────────────
  const submit = () => {
    const t = input.trim();
    if (status === "loading") { onStop(); return; }
    if (!t && !uploadDone) return;
    setAwaitChoice(false);
    onSend(t || "(process this file)");
    setInput("");
    setStagedFile(null);
    setUploadDone(false);
    requestAnimationFrame(() => taRef.current?.focus());
  };

  // ── Clarify option chosen ────────────────────────────────────────────────────
  const handlePickOption = (opt: ClarifyOption) => {
    setAwaitChoice(false);
    onPickOption(opt);
  };

  const placeholder = status === "loading"
    ? "Working… press Enter or ⏹ to stop"
    : awaitChoice
    ? "Click a button above or type your choice…"
    : stagedFile
    ? uploadDone
      ? `File ready — tell me what to do with "${stagedFile.name}"…`
      : `Uploading "${stagedFile.name}"…`
    : "Paste data or describe a sheet… (Shift+Enter for newline)";

  return (
    <div
      className="flex h-full flex-col bg-background"
      onDrop={onDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        ref={fileRef}
        type="file"
        className="hidden"
        accept=".csv,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.tiff,.webp,.docx,.txt"
        onChange={onFileInput}
      />

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {showWelcome && welcomeSlot}
        <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              onPickOption={handlePickOption}
              onDownload={onDownload}
              choicesDisabled={status === "loading"}
            />
          ))}

          {status === "loading" && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Sheet Agent is thinking…</span>
              <button
                onClick={onStop}
                className="ml-1 flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                title="Stop"
              >
                <Square className="h-3 w-3 fill-current" /> stop
              </button>
            </div>
          )}

          {awaitChoice && status === "idle" && (
            <p className="text-xs text-amber-500/80 animate-pulse ml-10">
              ↑ Click a button above to continue
            </p>
          )}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border bg-background/95 px-4 py-3 backdrop-blur">
        <div className={cn(
          "mx-auto flex max-w-3xl flex-col rounded-2xl border bg-card shadow-sm transition-all",
          awaitChoice
            ? "border-amber-500/40 focus-within:border-amber-400"
            : "border-border focus-within:border-primary/40 focus-within:shadow-md",
        )}>
          {/* File chip */}
          {stagedFile && (
            <div className="px-3 pt-2">
              <FileChip
                name={stagedFile.name}
                uploading={uploading}
                done={uploadDone}
                onRemove={() => { setStagedFile(null); setUploadDone(false); }}
              />
            </div>
          )}

          <div className="flex items-end gap-2 p-2">
            {/* Attach button */}
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              title="Attach file (CSV, Excel, PDF, Image)"
              className="mb-0.5 shrink-0 rounded-lg p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-40 transition-colors"
            >
              <Paperclip className="h-4 w-4" />
            </button>

            {/* Textarea */}
            <textarea
              ref={taRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              rows={1}
              placeholder={placeholder}
              className="max-h-40 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground"
            />

            {/* Stop (while loading) or Send button */}
            {status === "loading" ? (
              <Button
                size="icon"
                onClick={onStop}
                title="Stop (Enter)"
                className="mb-0.5 h-9 w-9 shrink-0 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
              >
                <Square className="h-4 w-4 fill-current" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={submit}
                disabled={(!input.trim() && !uploadDone) || uploading}
                title="Send (Enter)"
                className="mb-0.5 h-9 w-9 shrink-0 rounded-xl"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-muted-foreground">
          Drag & drop files · Enter to send · ⏹ to stop · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
