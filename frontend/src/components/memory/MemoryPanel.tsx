import { useState } from 'react'
import { Brain, Trash2 } from 'lucide-react'
import PreferencesPanel from './PreferencesPanel'
import HistoryPanel from './HistoryPanel'
import { useMemoryStore } from '../../store/memoryStore'
import { useMemory } from '../../hooks/useMemory'

type Tab = 'preferences' | 'history' | 'snippets'

export default function MemoryPanel() {
  const [tab, setTab] = useState<Tab>('preferences')
  const { snippets } = useMemoryStore()
  const { clearMemory } = useMemory()

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-800">
        <Brain size={12} className="text-purple-400" />
        <span className="text-xs font-semibold text-gray-300">Memory</span>
      </div>

      {/* Sub-tabs */}
      <div className="flex border-b border-gray-800">
        {(['preferences', 'history', 'snippets'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 text-xs capitalize transition-colors ${
              tab === t
                ? 'text-white border-b-2 border-purple-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t}
            {t === 'snippets' && snippets.length > 0 && (
              <span className="ml-1 text-[10px] text-purple-400">({snippets.length})</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'preferences' && <PreferencesPanel />}
        {tab === 'history'     && <HistoryPanel />}
        {tab === 'snippets'    && (
          <div className="p-3 space-y-2">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs text-gray-500">
                {snippets.length} learned fact(s)
              </p>
              {snippets.length > 0 && (
                <button
                  onClick={() => clearMemory(undefined)}
                  className="flex items-center gap-1 text-xs text-gray-600 hover:text-red-400"
                >
                  <Trash2 size={10} /> Clear
                </button>
              )}
            </div>
            {snippets.length === 0 && (
              <p className="text-xs text-gray-600">
                No learned facts yet. Facts are inferred automatically after each session.
              </p>
            )}
            {snippets.map((s, i) => (
              <div key={i} className="bg-gray-900 border border-gray-800 rounded p-2">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[10px] text-purple-400 font-mono">{s.key}</span>
                  <span className="text-[10px] text-gray-600">
                    {Math.round(s.confidence * 100)}% confident
                  </span>
                </div>
                <p className="text-xs text-gray-300">{s.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
