import { useAgentStore } from '../../store/agentStore'

export default function LogPanel() {
  const { logs } = useAgentStore()

  const levelColor: Record<string, string> = {
    info: 'text-gray-300',
    warning: 'text-amber-400',
    error: 'text-red-400',
  }

  return (
    <aside className="w-72 border-l border-gray-800 bg-gray-950 flex flex-col">
      <div className="px-3 py-2 border-b border-gray-800">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Execution Log</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5 font-mono">
        {logs.length === 0 && (
          <p className="text-xs text-gray-600 p-2">No activity yet.</p>
        )}
        {logs.map((log, i) => (
          <div key={i} className="flex gap-2 text-xs py-0.5">
            <span className="text-gray-600 shrink-0">{log.timestamp}</span>
            <span className="text-blue-400 shrink-0">[{log.agent}]</span>
            <span className={levelColor[log.level] || 'text-gray-300'}>{log.message}</span>
          </div>
        ))}
      </div>
    </aside>
  )
}
