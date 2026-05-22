import { useState } from 'react'
import { useAgentStore } from '../../store/agentStore'
import DiffViewer from '../diff/DiffViewer'
import FormulaPanel from '../formula/FormulaPanel'
import AnalyticsPanel from '../charts/AnalyticsPanel'
import ReflectionPanel from '../charts/ReflectionPanel'
import OCRPreview from '../ocr/OCRPreview'
import MemoryPanel from '../memory/MemoryPanel'
import { useMemory } from '../../hooks/useMemory'

type Tab = 'logs' | 'ocr' | 'diff' | 'formulas' | 'analytics' | 'reflection' | 'memory'

const TABS: { id: Tab; label: string }[] = [
  { id: 'logs',       label: 'Logs' },
  { id: 'ocr',        label: 'OCR' },
  { id: 'diff',       label: 'Diff' },
  { id: 'formulas',   label: 'Formulas' },
  { id: 'analytics',  label: 'Analytics' },
  { id: 'reflection', label: 'Quality' },
  { id: 'memory',     label: '🧠 Memory' },
]

const levelColor: Record<string, string> = {
  info:    'text-gray-300',
  warning: 'text-amber-400',
  error:   'text-red-400',
}

export default function RightPanel() {
  const [activeTab, setActiveTab] = useState<Tab>('logs')
  const { logs, sessionId, reflectionReport } = useAgentStore()
  useMemory()  // loads memory context on mount

  return (
    <aside className="w-80 border-l border-gray-800 bg-gray-950 flex flex-col">
      {/* Tabs */}
      <div className="flex border-b border-gray-800 overflow-x-auto scrollbar-hide">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-2.5 py-2 text-xs whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? 'text-white border-b-2 border-blue-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab.label}
            {tab.id === 'reflection' && reflectionReport && (
              <span className={`ml-1 text-[10px] font-bold ${
                reflectionReport.score >= 0.8 ? 'text-green-400' : 'text-amber-400'
              }`}>
                {Math.round(reflectionReport.score * 100)}%
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'logs' && (
          <div className="p-2 space-y-0.5 font-mono">
            {logs.length === 0 && (
              <p className="text-xs text-gray-600 p-2">No activity yet.</p>
            )}
            {logs.map((log, i) => (
              <div key={i} className="flex gap-2 text-xs py-0.5">
                <span className="text-gray-600 shrink-0">{log.timestamp}</span>
                <span className="text-blue-400 shrink-0 text-[10px]">[{log.agent}]</span>
                <span className={levelColor[log.level] || 'text-gray-300'}>{log.message}</span>
              </div>
            ))}
          </div>
        )}
        {activeTab === 'ocr'        && <OCRPreview />}
        {activeTab === 'diff'       && sessionId
          ? <DiffViewer sessionId={sessionId} />
          : activeTab === 'diff' && <p className="p-4 text-xs text-gray-500">Upload a file first.</p>
        }
        {activeTab === 'formulas'   && <FormulaPanel />}
        {activeTab === 'analytics'  && <AnalyticsPanel />}
        {activeTab === 'reflection' && <ReflectionPanel />}
        {activeTab === 'memory'     && <MemoryPanel />}
      </div>
    </aside>
  )
}
