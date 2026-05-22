import { useState } from 'react'
import Sidebar from './components/layout/Sidebar'
import ChatPanel from './components/layout/ChatPanel'
import RightPanel from './components/layout/RightPanel'
import ApprovalQueue from './components/approval/ApprovalQueue'
import { useWebSocket } from './hooks/useWebSocket'
import { useAgentStore } from './store/agentStore'

export default function App() {
  const { sessionId } = useAgentStore()
  useWebSocket(sessionId)

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Left: Workspace explorer */}
      <Sidebar />

      {/* Center: Chat */}
      <main className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <div className="flex-1 overflow-hidden">
          <ChatPanel />
        </div>
        <ApprovalQueue />
      </main>

      {/* Right: Detailed panels */}
      <RightPanel />
    </div>
  )
}

function TopBar() {
  const { status, schemaType, sessionId } = useAgentStore()

  const statusColor: Record<string, string> = {
    idle: 'bg-gray-600',
    running: 'bg-blue-500 animate-pulse',
    awaiting_approval: 'bg-amber-500',
    complete: 'bg-green-500',
    error: 'bg-red-500',
  }

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900">
      <div className="flex items-center gap-3">
        <span className="font-semibold text-sm tracking-tight text-white">
          SheetAgent <span className="text-blue-400">AI</span>
        </span>
        {schemaType && (
          <span className="text-xs px-2 py-0.5 rounded bg-blue-900 text-blue-300">
            {schemaType}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-400">
        {sessionId && <span className="font-mono">#{sessionId.slice(0, 8)}</span>}
        <span className={`w-2 h-2 rounded-full ${statusColor[status] || 'bg-gray-600'}`} />
        <span className="capitalize">{status}</span>
      </div>
    </div>
  )
}
