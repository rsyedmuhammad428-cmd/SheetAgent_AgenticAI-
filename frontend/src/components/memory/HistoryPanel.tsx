import { useMemoryStore } from '../../store/memoryStore'
import { FileSpreadsheet, Clock, Star } from 'lucide-react'

const schemaColors: Record<string, string> = {
  invoice:      'bg-blue-900 text-blue-300',
  sales_report: 'bg-green-900 text-green-300',
  inventory:    'bg-amber-900 text-amber-300',
  hr_records:   'bg-purple-900 text-purple-300',
  financial:    'bg-emerald-900 text-emerald-300',
  generic:      'bg-gray-800 text-gray-400',
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function HistoryPanel() {
  const { recentSessions } = useMemoryStore()

  if (recentSessions.length === 0) {
    return (
      <div className="p-4 text-xs text-gray-500">
        No sessions yet. Process your first file to build history.
      </div>
    )
  }

  return (
    <div className="p-3 space-y-2">
      <p className="text-xs text-gray-500">{recentSessions.length} recent session(s)</p>
      {recentSessions.map((s) => (
        <div key={s.session_id} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-2 min-w-0">
              <FileSpreadsheet size={12} className="text-green-400 shrink-0" />
              <span className="text-xs text-gray-200 truncate font-medium">
                {s.file_name || 'Unknown file'}
              </span>
            </div>
            {s.quality_score !== null && s.quality_score !== undefined && (
              <div className="flex items-center gap-1 shrink-0">
                <Star size={10} className="text-amber-400" />
                <span className="text-xs text-amber-400">
                  {Math.round(s.quality_score * 100)}%
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-1.5 mb-1.5">
            {s.schema_type && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                schemaColors[s.schema_type] || schemaColors.generic
              }`}>
                {s.schema_type.replace('_', ' ')}
              </span>
            )}
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
              {s.row_count} rows
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
              {s.col_count} cols
            </span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${
              s.status === 'complete'
                ? 'bg-green-900 text-green-400'
                : 'bg-red-900 text-red-400'
            }`}>
              {s.status}
            </span>
          </div>

          <div className="flex items-center gap-1 text-[10px] text-gray-600">
            <Clock size={9} />
            {s.created_at ? timeAgo(s.created_at) : 'Unknown time'}
          </div>
        </div>
      ))}
    </div>
  )
}
