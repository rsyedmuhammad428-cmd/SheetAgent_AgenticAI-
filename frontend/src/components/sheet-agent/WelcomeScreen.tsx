/**
 * WelcomeScreen.tsx — fully responsive
 *
 * Mobile : single-column cards, smaller heading
 * Tablet : same, slightly larger
 * Desktop: 3-column cards, large heading
 */
import { Table2, BarChart3, FileSpreadsheet } from "lucide-react";

const SUGGESTIONS = [
  {
    icon:   Table2,
    title:  "Create a sheet",
    prompt: "Create a student marksheet with Math, Science, English columns",
    desc:   "Paste rows like 'Ali 85, Sara 92' to build a clean table.",
  },
  {
    icon:   BarChart3,
    title:  "Visualize data",
    prompt: "Create a bar chart by subject from my student data",
    desc:   "Ask for a bar, line, or pie chart from any column.",
  },
  {
    icon:   FileSpreadsheet,
    title:  "Full dashboard",
    prompt: "Create a full financial report with KPI dashboard and charts",
    desc:   "Sheet + charts + summary, generated in one go.",
  },
];

interface WelcomeScreenProps {
  onPick:    (text: string) => void;
  greeting?: string;
  userName?: string;
}

export function WelcomeScreen({
  onPick,
  greeting = "Good morning",
  userName,
}: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center animate-fade-in sm:px-6 sm:py-16">
      {/* Heading — scales from mobile to desktop */}
      <h1 className="font-serif text-3xl font-normal tracking-tight text-primary sm:text-4xl lg:text-5xl">
        ✦ {greeting}{userName ? `, ${userName}` : ""}
      </h1>
      <p className="mt-2 font-serif text-lg text-primary/70 sm:text-xl lg:text-2xl">
        ready to build a sheet?
      </p>
      <p className="mt-3 max-w-sm text-sm text-muted-foreground sm:max-w-xl sm:text-base">
        Paste raw data, upload a CSV or PDF, or describe what you want — I'll
        build the table, charts, and dashboard.
      </p>

      {/* Suggestion cards — 1 col on mobile, 3 on md+ */}
      <div className="mt-8 grid w-full max-w-3xl grid-cols-1 gap-3 sm:mt-10 md:grid-cols-3">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            onClick={() => onPick(s.prompt)}
            className="group rounded-xl border border-border bg-card p-4 text-left transition hover:border-primary/40 hover:shadow-md active:scale-95"
          >
            <s.icon className="mb-2 h-5 w-5 text-primary transition group-hover:scale-110" />
            <div className="text-sm font-semibold text-foreground">{s.title}</div>
            <div className="mt-1 text-xs text-muted-foreground">{s.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
