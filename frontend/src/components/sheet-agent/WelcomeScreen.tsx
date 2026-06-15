import { Table2, BarChart3, FileSpreadsheet } from "lucide-react";

const SUGGESTIONS = [
  {
    icon: Table2,
    title: "Create a sheet",
    desc: "Paste rows like 'Ali 85, Sara 92' to build a clean table.",
  },
  {
    icon: BarChart3,
    title: "Visualize data",
    desc: "Ask for a bar, line, or pie chart from any column.",
  },
  {
    icon: FileSpreadsheet,
    title: "Full dashboard",
    desc: "Sheet + charts + summary, generated in one go.",
  },
];

export function WelcomeScreen({ onPick }: { onPick: (text: string) => void }) {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center animate-fade-in">
      <h1 className="font-serif text-4xl font-normal tracking-tight text-primary sm:text-5xl">
        ✦ {greeting}, ready to build a sheet?
      </h1>
      <p className="mt-4 max-w-xl text-base text-muted-foreground">
        Paste raw data, upload a CSV or PDF, or describe what you want — I'll build the table, charts, and dashboard.
      </p>

      <div className="mt-10 grid w-full max-w-3xl grid-cols-1 gap-3 sm:grid-cols-3">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            onClick={() => onPick(s.title)}
            className="group rounded-xl border border-border bg-card p-4 text-left transition hover:border-primary/40 hover:shadow-md"
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
