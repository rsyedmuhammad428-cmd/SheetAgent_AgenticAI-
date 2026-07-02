/**
 * ChatPanel.tsx — fully responsive (mobile, tablet, desktop)
 *
 * Changes for responsiveness:
 *  - Message bubbles: max-w-[85%] on mobile → max-w-[75%] on desktop
 *  - Input: full-width, no horizontal margin on mobile; centred max-w on desktop
 *  - File chip: truncates long names on small screens
 *  - Download card: stacks vertically on xs screens
 *  - Clarify buttons: wrap on small screens
 *  - Stop/Send buttons: always visible (not clipped)
 */
import { useEffect, useRef, useState } from "react";
import {
  Send, Loader2, Sparkles, Paperclip, X,
  Square, Download, FileSpreadsheet, CheckCheck,
} from "lucide-react";
import type { ChatMessage, ClarifyOption } from "@/lib/sheet-agent";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { HumanInLoopThemePicker, HumanInLoopGraphPicker } from "./HumanInLoopPicker";

interface UploadResult {
  session_id: string; file_name: string;
  file_type: string;  file_path: string; message: string;
}

interface ChatPanelProps {
  messages: ChatMessage[];
  status: "idle" | "loading";
  onSend: (text: string, attachedFileName?: string) => void;
  onStop: () => void;
  onUpload: (file: File) => Promise<UploadResult>;
  onDownload: (filename: string) => Promise<void>;
  onPickOption: (opt: ClarifyOption) => void;
  showWelcome: boolean;
  welcomeSlot?: React.ReactNode;
}

function FileChip({ name, uploading, done, onRemove }: {
  name: string; uploading: boolean; done: boolean; onRemove: () => void;
}) {
  return (
    <div className="flex max-w-[200px] items-center gap-2 rounded-lg border border-border bg-muted px-2.5 py-1.5 text-xs sm:max-w-xs">
      {uploading
        ? <Loader2 className="h-3 w-3 animate-spin shrink-0 text-primary" />
        : <span className="shrink-0">📎</span>}
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

function DownloadCard({ filename, title, onDownload }: {
  filename: string; title?: string; onDownload: (f: string) => Promise<void>;
}) {
  const [st, setSt] = useState<"idle" | "loading" | "done" | "error">("idle");
  async function handle() {
    setSt("loading");
    try { await onDownload(filename); setSt("done"); setTimeout(() => setSt("idle"), 4000); }
    catch { setSt("error"); setTimeout(() => setSt("idle"), 3000); }
  }
  const colors = {
    idle: "bg-green-600 hover:bg-green-500", loading: "bg-green-700 opacity-60",
    done: "bg-emerald-700", error: "bg-red-700 hover:bg-red-600",
  };
  const labels = {
    idle: "Download Excel", loading: "Downloading…",
    done: "Downloaded ✓",  error:   "Retry",
  };
  return (
    <div className="mt-2 flex flex-col gap-2 rounded-xl border border-green-700/40 bg-green-900/20 p-3 sm:flex-row sm:items-center">
      <FileSpreadsheet className="hidden h-5 w-5 shrink-0 text-green-400 sm:block" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-green-300">{title ?? filename}</p>
        <p className="truncate text-[11px] text-green-600">{filename}</p>
      </div>
      <button
        onClick={handle}
        disabled={st === "loading"}
        className={cn(
          "flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold text-white transition-all sm:w-auto",
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

function ClarifyButtons({ options, onPick, disabled }: {
  options: ClarifyOption[]; onPick: (opt: ClarifyOption) => void; disabled: boolean;
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
            "rounded-full border px-3 py-1.5 text-xs transition active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed",
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

function MessageBubble({ message, onPickOption, onDownload, choicesDisabled }: {
  message: ChatMessage;
  onPickOption: (opt: ClarifyOption) => void;
  onDownload: (filename: string) => Promise<void>;
  choicesDisabled: boolean;
}) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex w-full animate-fade-in", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("flex gap-2 sm:gap-3", isUser ? "max-w-[88%] flex-row-reverse sm:max-w-[80%]" : "max-w-[92%] sm:max-w-[85%]", (message.trigger === "hitl_theme" || message.trigger === "hitl_graph") && "max-w-full sm:max-w-full w-full")}>
        {!isUser && (
          <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-fuchsia-500 text-white sm:h-7 sm:w-7">
            <Sparkles className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className={cn(
            "rounded-2xl px-3 py-2 text-sm leading-relaxed sm:px-4 sm:py-2.5",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
            (message.trigger === "hitl_theme" || message.trigger === "hitl_graph") && "bg-gradient-to-br from-card to-muted/60 border border-primary/20 shadow-md",
          )}>
            {/* Attached file chip — only on user messages that had a file */}
            {isUser && message.attachedFileName && (
              <div className="mb-1.5 flex items-center gap-1.5 rounded-lg bg-white/15 px-2 py-1 text-xs">
                <Paperclip className="h-3 w-3 shrink-0" />
                <span className="truncate max-w-[160px] sm:max-w-xs">{message.attachedFileName}</span>
              </div>
            )}
            <div className="whitespace-pre-wrap break-words">
              {message.text.split(/\*\*(.*?)\*\*/g).map((part, i) =>
                i % 2 === 1
                  ? <strong key={i} className="font-semibold">{part}</strong>
                  : part
              )}
            </div>
            {message.trigger === "clarify" && message.options && (
              <ClarifyButtons options={message.options} onPick={onPickOption} disabled={choicesDisabled} />
            )}
            {/* ── HITL Theme Picker ── */}
            {message.trigger === "hitl_theme" && message.options && (
              <HumanInLoopThemePicker
                options={message.options}
                onPick={onPickOption}
                disabled={choicesDisabled}
              />
            )}
            {/* ── HITL Graph Picker ── */}
            {message.trigger === "hitl_graph" && message.options && (
              <HumanInLoopGraphPicker
                options={message.options}
                onPick={onPickOption}
                disabled={choicesDisabled}
              />
            )}
          </div>
          {message.trigger === "download" && message.filename && (
            <DownloadCard filename={message.filename} title={message.fileTitle} onDownload={onDownload} />
          )}
        </div>
      </div>
    </div>
  );
}

export function ChatPanel({
  messages, status, onSend, onStop, onUpload, onDownload,
  onPickOption, showWelcome, welcomeSlot,
}: ChatPanelProps) {
  const [input,      setInput]      = useState("");
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [uploading,  setUploading]  = useState(false);
  const [uploadDone, setUploadDone] = useState(false);
  const [awaitChoice, setAwaitChoice] = useState(false);

  const taRef     = useRef<HTMLTextAreaElement>(null);
  const fileRef   = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, status]);

  useEffect(() => { taRef.current?.focus(); }, []);

  useEffect(() => {
    const last = messages[messages.length - 1];
    const hitlTriggers = ["clarify", "hitl_theme", "hitl_graph"] as const;
    setAwaitChoice(last?.role === "assistant" && hitlTriggers.includes(last?.trigger as typeof hitlTriggers[number]));
  }, [messages]);

  async function handleFileAttach(file: File) {
    setStagedFile(file); setUploading(true); setUploadDone(false);
    try { await onUpload(file); setUploadDone(true); taRef.current?.focus(); }
    catch { setStagedFile(null); }
    finally { setUploading(false); }
  }

  const submit = () => {
    const t = input.trim();
    if (status === "loading") { onStop(); return; }
    if (!t && !uploadDone) return;
    setAwaitChoice(false);
    const attachedFileName = stagedFile?.name;
    onSend(t || "(process this file)", attachedFileName);
    setInput(""); setStagedFile(null); setUploadDone(false);
    requestAnimationFrame(() => taRef.current?.focus());
  };

  // Detect if last message is HITL step
  const lastMsg = messages[messages.length - 1];
  const isHitlTheme = lastMsg?.trigger === "hitl_theme";
  const isHitlGraph = lastMsg?.trigger === "hitl_graph";

  const placeholder = status === "loading"
    ? "Working… press Enter or ⏹ to stop"
    : isHitlTheme
    ? "👆 Choose a color theme above to continue…"
    : isHitlGraph
    ? "👆 Choose a chart type above to continue…"
    : awaitChoice
    ? "Click a button above or type your choice…"
    : stagedFile
    ? uploadDone
      ? `File ready — describe what to do…`
      : `Uploading "${stagedFile.name}"…`
    : "Paste data or describe a sheet…";

  return (
    <div
      className="flex h-full flex-col bg-background"
      onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) handleFileAttach(f); }}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        ref={fileRef} type="file" className="hidden"
        accept=".csv,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.tiff,.webp,.docx,.txt"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileAttach(f); e.target.value = ""; }}
      />

      {/* Messages scroll area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto overscroll-auto scroll-smooth">
        {showWelcome && welcomeSlot}
        <div className="mx-auto max-w-3xl space-y-3 px-3 py-4 sm:space-y-4 sm:px-4 sm:py-6">
          {messages.map((m) => (
            <MessageBubble
              key={m.id} message={m}
              onPickOption={(opt) => { setAwaitChoice(false); onPickOption(opt); }}
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
            <p className="animate-pulse text-xs text-amber-500/80 ml-9">
              ↑ Click a button above to continue
            </p>
          )}
        </div>
      </div>

      {/* Input bar — sticks to bottom */}
      <div className="shrink-0 border-t border-border bg-background/95 px-3 py-2 backdrop-blur sm:px-4 sm:py-3">
        <div className={cn(
          "mx-auto flex max-w-3xl flex-col rounded-2xl border bg-card shadow-sm transition-all",
          awaitChoice
            ? "border-amber-500/40 focus-within:border-amber-400"
            : "border-border focus-within:border-primary/40 focus-within:shadow-md",
        )}>
          {stagedFile && (
            <div className="px-3 pt-2">
              <FileChip
                name={stagedFile.name} uploading={uploading} done={uploadDone}
                onRemove={() => { setStagedFile(null); setUploadDone(false); }}
              />
            </div>
          )}

          <div className="flex items-end gap-1.5 p-2 sm:gap-2">
            {/* Attach */}
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              title="Attach file"
              className="mb-0.5 shrink-0 rounded-lg p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-40 transition-colors touch-manipulation"
            >
              <Paperclip className="h-4 w-4" />
            </button>

            {/* Textarea — auto-grows */}
            <textarea
              ref={taRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // Auto-grow
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
              }}
              rows={1}
              placeholder={placeholder}
              className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-1 py-2 text-sm outline-none placeholder:text-muted-foreground sm:px-2"
            />

            {/* Stop / Send */}
            {status === "loading" ? (
              <Button
                size="icon" onClick={onStop} title="Stop"
                className="mb-0.5 h-9 w-9 shrink-0 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 touch-manipulation"
              >
                <Square className="h-4 w-4 fill-current" />
              </Button>
            ) : (
              <Button
                size="icon" onClick={submit}
                disabled={(!input.trim() && !uploadDone) || uploading}
                title="Send (Enter)"
                className="mb-0.5 h-9 w-9 shrink-0 rounded-xl touch-manipulation"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Footer */}
        <p className="mx-auto mt-1.5 max-w-3xl text-center text-[10px] text-muted-foreground sm:text-[11px]">
          AI Sheet Agent can make mistakes.Please double-check responses
       
          
        </p>
      </div>
    </div>
  );
}
