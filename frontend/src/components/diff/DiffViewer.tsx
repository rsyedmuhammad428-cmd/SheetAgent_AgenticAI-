import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

interface DiffEntry {
  row: number
  column: string
  before: unknown
  after: unknown
  change_type: 'modified' | 'removed' | 'added'
}

interface DiffSummary {
  total_changes: number
  modified_cells: number
  removed_rows: number
  added_rows: number
  affected_columns: Record<string, number>
}

interface DiffResponse {
  diff: DiffEntry[]
  summary: DiffSummary
}

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const changeColors = {
  modified: { row: 'bg-amber-950/40', badge: 'bg-amber-900 text-amber-300', label: 'MODIFIED' },
  removed:  { row: 'bg-red-950/40',   badge: 'bg-red-900 text-red-300',     label: 'REMOVED'  },
  added:    { row: 'bg-green-950/40', badge: 'bg-green-900 text-green-300', label: 'ADDED'    },
}

export default function DiffViewer({ sessionId }: { sessionId: string }) {
  const { data, isLoading, error } = useQuery<DiffResponse>({
    queryKey: ['diff', sessionId],
    queryFn: async () => {
      const { data } = await axios.get(`${API}/api/p2/diff/${sessionId}?limit=100`)
      return data
    },
    enabled: !!sessionId,
  })

  if (isLoading) return <div className="p-4 text-xs text-gray-500 animate-pulse">Loading diff...</div>
  if (error)     return <div className="p-4 text-xs text-red-400">Could not load diff.</div>
  if (!data || data.diff.length === 0) {
    return <div className="p-4 text-xs text-gray-500">No changes detected — data was already clean.</div>
  }

  const { summary, diff } = data

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* Summary bar */}
      <div className="grid grid-cols-4 gap-2">
        {[
          { label: 'Total Changes', value: summary.total_changes, color: 'text-white' },
          { label: 'Cells Modified', value: summary.modified_cells, color: 'text-amber-400' },
          { label: 'Rows Removed', value: summary.removed_rows, color: 'text-red-400' },
          { label: 'Rows Added', value: summary.added_rows, color: 'text-green-400' },
        ].map(s => (
          <div key={s.label} className="bg-gray-900 rounded-lg p-2 text-center">
            <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Affected columns */}
      {Object.keys(summary.affected_columns).length > 0 && (
        <div className="flex flex-wrap gap-1">
          <span className="text-xs text-gray-500">Columns:</span>
          {Object.entries(summary.affected_columns).map(([col, count]) => (
            <span key={col} className="text-xs bg-gray-800 px-2 py-0.5 rounded text-gray-300">
              {col} <span className="text-gray-500">({count})</span>
            </span>
          ))}
        </div>
      )}

      {/* Diff table */}
      <div className="overflow-auto max-h-80 rounded-lg border border-gray-800">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-gray-900">
            <tr>
              {['Row', 'Column', 'Type', 'Before', 'After'].map(h => (
                <th key={h} className="text-left px-3 py-2 text-gray-500 font-medium border-b border-gray-800">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {diff.map((entry, i) => {
              const style = changeColors[entry.change_type] || changeColors.modified
              return (
                <tr key={i} className={`${style.row} border-b border-gray-800/50`}>
                  <td className="px-3 py-1.5 text-gray-400 font-mono">{entry.row}</td>
                  <td className="px-3 py-1.5 text-gray-300">{entry.column}</td>
                  <td className="px-3 py-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${style.badge}`}>
                      {style.label}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-red-300 font-mono max-w-[120px] truncate">
                    {String(entry.before ?? '—')}
                  </td>
                  <td className="px-3 py-1.5 text-green-300 font-mono max-w-[120px] truncate">
                    {String(entry.after ?? '—')}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
