import { Check, X, Settings } from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import { approveSuggestion, approveAll } from '../../api/client'

export default function ApprovalQueue() {
  const { sessionId, suggestions, status, setSuggestions } = useAgentStore()

  const pending = suggestions.filter(s => s.approved === undefined || s.approved === null)

  if (status !== 'awaiting_approval' || pending.length === 0) return null

  const handleApprove = async (id: string, approved: boolean) => {
    if (!sessionId) return
    await approveSuggestion(sessionId, id, approved)
    setSuggestions(suggestions.map(s => s.id === id ? { ...s, approved } : s))
  }

  const handleApproveAll = async () => {
    if (!sessionId) return
    await approveAll(sessionId)
    setSuggestions(suggestions.map(s => ({ ...s, approved: true })))
  }

  return (
    <div className="border-t border-gray-800 bg-gray-900 px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
          Approval Queue — {pending.length} suggestions
        </span>
        <button
          onClick={handleApproveAll}
          className="text-xs bg-green-700 hover:bg-green-600 text-white px-3 py-1 rounded"
        >
          Accept All
        </button>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {pending.map(s => (
          <div
            key={s.id}
            className="flex-shrink-0 bg-gray-800 border border-gray-700 rounded-lg p-3 w-64"
          >
            <p className="text-xs font-medium text-gray-200 mb-1">{s.title}</p>
            <p className="text-xs text-gray-500 mb-2 line-clamp-2">{s.description}</p>
            <div className="flex gap-1">
              <button
                onClick={() => handleApprove(s.id, true)}
                className="flex items-center gap-1 text-xs bg-green-800 hover:bg-green-700 text-green-200 px-2 py-1 rounded"
              >
                <Check size={10} /> Accept
              </button>
              <button
                onClick={() => handleApprove(s.id, false)}
                className="flex items-center gap-1 text-xs bg-red-900 hover:bg-red-800 text-red-300 px-2 py-1 rounded"
              >
                <X size={10} /> Reject
              </button>
              <button className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded">
                <Settings size={10} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
