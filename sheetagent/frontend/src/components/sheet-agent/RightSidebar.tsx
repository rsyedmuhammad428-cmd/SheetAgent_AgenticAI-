import { FileSpreadsheet, BarChart3, FileText, Sparkles } from "lucide-react";
import type { AgentFile } from "@/lib/sheet-agent";
import { cn } from "@/lib/utils";

const ICONS = {
  sheet: FileSpreadsheet,
  chart: BarChart3,
  doc: FileText,
} as const;

export function RightSidebar({
  files,
  activeId,
  onSelect,
}: {
  files: AgentFile[];
  activeId?: string;
  onSelect?: (id: string) => void;
}) {
  return (
    <aside className="flex h-full w-72 flex-col border-l border-border bg-sidebar">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Sparkles className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">Workspace</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {files.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
            Files and charts you create will appear here.
          </div>
        ) : (
          <ul className="space-y-1.5">
            {files.map((f) => {
              const Icon = ICONS[f.kind];
              return (
                <li key={f.id}>
                  <button
                    onClick={() => onSelect?.(f.id)}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition",
                      activeId === f.id
                        ? "bg-primary/10 text-primary"
                        : "hover:bg-accent",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{f.name}</div>
                      <div className="text-[10px] text-muted-foreground">
                        {new Date(f.createdAt).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
