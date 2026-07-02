/**
 * HumanInLoopPicker.tsx
 *
 * Renders two special interactive UI steps for the Human-in-the-Loop workflow:
 *   1. HumanInLoopThemePicker  — 8 color theme swatches
 *   2. HumanInLoopGraphPicker  — 3 chart type cards (bar/pie/line)
 *
 * Both call onPick(option) when the user selects, which sends __choice:<id>
 * back to the backend to advance the HITL state machine.
 */
import { useState } from "react";
import { CheckCircle2, BarChart3, PieChart, TrendingUp, Loader2 } from "lucide-react";
import type { ClarifyOption } from "@/lib/sheet-agent";
import { cn } from "@/lib/utils";

// ── Shared ────────────────────────────────────────────────────────────────────

interface PickerProps {
  options: ClarifyOption[];
  onPick: (opt: ClarifyOption) => void;
  disabled: boolean;
}

// ── Theme Picker ──────────────────────────────────────────────────────────────

export function HumanInLoopThemePicker({ options, onPick, disabled }: PickerProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function pick(opt: ClarifyOption) {
    if (disabled || loading) return;
    setSelected(opt.id);
    setLoading(true);
    onPick(opt);
  }

  return (
    <div className="mt-3 space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {options.map((opt) => {
          const isSelected = selected === opt.id;
          // Extract colors — backend sends hex strings with #
          const headerColor = opt.header ?? "#1E3A5F";
          const rowAltColor = opt.row_alt ?? "#D6E4F0";

          return (
            <button
              key={opt.id}
              onClick={() => pick(opt)}
              disabled={disabled || loading}
              className={cn(
                "group relative flex flex-col overflow-hidden rounded-xl border-2 text-left transition-all duration-200",
                "hover:scale-[1.03] hover:shadow-lg active:scale-[0.97]",
                "disabled:cursor-not-allowed disabled:opacity-50",
                isSelected
                  ? "border-primary ring-2 ring-primary/30 shadow-lg scale-[1.03]"
                  : "border-border hover:border-primary/50",
              )}
              title={opt.label}
            >
              {/* Color preview — mini Excel-like swatch */}
              <div className="h-14 w-full flex flex-col overflow-hidden">
                {/* Header row swatch */}
                <div
                  className="h-5 w-full flex-shrink-0"
                  style={{ backgroundColor: headerColor }}
                />
                {/* Alternating rows preview */}
                {[rowAltColor, "#FFFFFF", rowAltColor].map((bg, i) => (
                  <div
                    key={i}
                    className="flex-1 w-full"
                    style={{ backgroundColor: bg }}
                  />
                ))}
              </div>

              {/* Label */}
              <div className="bg-card px-2 py-1.5">
                <p className="truncate text-[11px] font-medium text-foreground leading-tight">
                  {opt.label}
                </p>
              </div>

              {/* Selected badge */}
              {isSelected && (
                <div className="absolute top-1 right-1 rounded-full bg-primary p-0.5">
                  {loading
                    ? <Loader2 className="h-3 w-3 text-white animate-spin" />
                    : <CheckCircle2 className="h-3 w-3 text-white" />}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {selected && (
        <p className="animate-pulse text-xs text-primary/80 text-center">
          ✓ Theme selected — loading chart options…
        </p>
      )}
    </div>
  );
}

// ── Graph Picker ──────────────────────────────────────────────────────────────

const GRAPH_ICONS: Record<string, React.ReactNode> = {
  "graph_bar":  <BarChart3  className="h-8 w-8" />,
  "graph_pie":  <PieChart   className="h-8 w-8" />,
  "graph_line": <TrendingUp className="h-8 w-8" />,
};

const GRAPH_PREVIEWS: Record<string, React.ReactNode> = {
  "graph_bar": (
    <div className="flex items-end gap-1 h-10 px-1">
      {[40, 75, 55, 90, 65].map((h, i) => (
        <div
          key={i}
          className="flex-1 rounded-sm bg-primary/70"
          style={{ height: `${h}%` }}
        />
      ))}
    </div>
  ),
  "graph_pie": (
    <div className="flex items-center justify-center h-10">
      <svg viewBox="0 0 36 36" className="h-10 w-10">
        {/* Pie: 45% blue, 30% purple, 25% emerald */}
        <circle cx="18" cy="18" r="15" fill="transparent"
          stroke="hsl(var(--primary))" strokeWidth="30"
          strokeDasharray="42 100" strokeDashoffset="25" />
        <circle cx="18" cy="18" r="15" fill="transparent"
          stroke="#a78bfa" strokeWidth="30"
          strokeDasharray="28 100" strokeDashoffset="-17" />
        <circle cx="18" cy="18" r="15" fill="transparent"
          stroke="#34d399" strokeWidth="30"
          strokeDasharray="30 100" strokeDashoffset="-45" />
        <circle cx="18" cy="18" r="6" fill="hsl(var(--background))" />
      </svg>
    </div>
  ),
  "graph_line": (
    <div className="flex items-end h-10 px-1">
      <svg viewBox="0 0 80 40" className="w-full h-full">
        <polyline
          points="0,35 15,22 30,28 45,10 60,18 80,5"
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {[0,15,30,45,60,80].map((x, i) => {
          const ys = [35,22,28,10,18,5];
          return <circle key={i} cx={x} cy={ys[i]} r="2.5" fill="hsl(var(--primary))" />;
        })}
      </svg>
    </div>
  ),
};

export function HumanInLoopGraphPicker({ options, onPick, disabled }: PickerProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function pick(opt: ClarifyOption) {
    if (disabled || loading) return;
    setSelected(opt.id);
    setLoading(true);
    onPick(opt);
  }

  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        {options.map((opt) => {
          const isSelected = selected === opt.id;
          const icon       = GRAPH_ICONS[opt.id];
          const preview    = GRAPH_PREVIEWS[opt.id];

          return (
            <button
              key={opt.id}
              onClick={() => pick(opt)}
              disabled={disabled || loading}
              className={cn(
                "group relative flex-1 flex flex-col gap-2 rounded-xl border-2 p-3 text-left transition-all duration-200",
                "hover:scale-[1.02] hover:shadow-lg active:scale-[0.98]",
                "disabled:cursor-not-allowed disabled:opacity-50",
                isSelected
                  ? "border-primary ring-2 ring-primary/30 bg-primary/5 shadow-lg"
                  : "border-border hover:border-primary/40 bg-card",
              )}
            >
              {/* Mini chart preview */}
              <div className="rounded-lg bg-muted/50 px-2 pt-2 pb-1">
                {preview}
              </div>

              {/* Icon + label */}
              <div className="flex items-center gap-2">
                <span className={cn(
                  "text-muted-foreground group-hover:text-primary transition-colors",
                  isSelected && "text-primary",
                )}>
                  {icon}
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground">{opt.label}</p>
                  {opt.desc && (
                    <p className="text-[11px] text-muted-foreground leading-tight">{opt.desc}</p>
                  )}
                </div>
              </div>

              {/* Selected checkmark */}
              {isSelected && (
                <div className="absolute top-2 right-2">
                  {loading
                    ? <Loader2 className="h-4 w-4 text-primary animate-spin" />
                    : <CheckCircle2 className="h-4 w-4 text-primary" />}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {selected && (
        <p className="animate-pulse text-xs text-primary/80 text-center">
          ✓ Chart selected — creating your Excel sheet…
        </p>
      )}
    </div>
  );
}
