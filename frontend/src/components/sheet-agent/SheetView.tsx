import type { SheetData } from "@/lib/sheet-agent";

export function SheetView({ sheet }: { sheet: SheetData }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      {sheet.title && (
        <div className="border-b border-border px-4 py-2 text-sm font-semibold">
          {sheet.title}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-muted/50">
            <tr>
              {sheet.columns.map((c) => (
                <th
                  key={c}
                  className="border-b border-border px-3 py-2 text-left font-medium text-foreground"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sheet.rows.map((row, i) => (
              <tr key={i} className="hover:bg-muted/30">
                {row.map((cell, j) => (
                  <td key={j} className="border-b border-border px-3 py-2 text-foreground">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
