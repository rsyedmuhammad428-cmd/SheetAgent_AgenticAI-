import { useState, useRef, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Upload, Send, Download, FileSpreadsheet,
  Loader, CheckCheck, ChevronRight
} from 'lucide-react'
import axios from 'axios'
import { uploadFile, runAgent, approveAll } from '../../api/client'
import { useAgentStore } from '../../store/agentStore'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Message {
  id: string
  role: 'user' | 'agent' | 'system'
  text: string
  timestamp: string
  action?: {
    trigger?: string
    filename?: string
    download_url?: string
    title?: string
  }
}

const QUICK_PROMPTS = [
  'Create an invoice template',
  'Monthly sales report with charts',
  'Employee HR records sheet',
  'Budget tracker with formulas',
  'Student grade sheet',
  'Inventory management sheet',
]

function DownloadButton({ filename, url, title }: { filename: string; url: string; title?: string }) {
  const [downloading, setDownloading] = useState(false)
  const [done, setDone] = useState(false)

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const response = await axios.get(`${API}${url}`, { responseType: 'blob' })
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = filename
      link.click()
      URL.revokeObjectURL(link.href)
      setDone(true)
      setTimeout(() => setDone(false), 3000)
    } catch (e) {
      console.error('Download failed:', e)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="mt-3 flex items-center gap-3 bg-green-900/30 border border-green-700/50 rounded-lg p-3">
      <FileSpreadsheet size={20} className="text-green-400 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-green-300 truncate">
          {title || filename}
        </p>
        <p className="text-[10px] text-green-600 truncate">{filename}</p>
      </div>
      <button
        onClick={handleDownload}
        disabled={downloading}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
          done
            ? 'bg-green-700 text-white'
            : 'bg-green-600 hover:bg-green-500 text-white'
        } disabled:opacity-60`}
      >
        {downloading ? (
          <Loader size={12} className="animate-spin" />
        ) : done ? (
          <CheckCheck size={12} />
        ) : (
          <Download size={12} />
        )}
        {downloading ? 'Downloading...' : done ? 'Downloaded!' : 'Download Excel'}
      </button>
    </div>
  )
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-blue-700 flex items-center justify-center mr-2 mt-1 shrink-0 text-[9px] font-bold text-white">
          AI
        </div>
      )}
      <div className={`max-w-[85%] ${isSystem ? 'w-full max-w-full' : ''}`}>
        <div className={`px-3 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-sm'
            : isSystem
            ? 'bg-gray-800/50 text-gray-400 text-xs border border-gray-800 rounded-lg'
            : 'bg-gray-800 text-gray-200 rounded-bl-sm'
        }`}>
          {/* Render markdown-like bold */}
          {msg.text.split('\n').map((line, i) => (
            <p key={i} className={i > 0 ? 'mt-1' : ''}>
              {line.split(/\*\*(.*?)\*\*/).map((part, j) =>
                j % 2 === 1
                  ? <strong key={j} className="font-semibold">{part}</strong>
                  : part
              )}
            </p>
          ))}
        </div>

        {/* Download button — shown when action has download trigger */}
        {msg.action?.trigger === 'download' && msg.action.download_url && (
          <DownloadButton
            filename={msg.action.filename!}
            url={msg.action.download_url}
            title={msg.action.title}
          />
        )}

        <p className={`text-[10px] mt-1 ${isUser ? 'text-right text-blue-300' : 'text-gray-600'}`}>
          {msg.timestamp}
        </p>
      </div>
    </div>
  )
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([{
    id: '0',
    role: 'agent',
    text: 'Welcome to **SheetAgent AI**! I can:\n• Process uploaded CSV, Excel, PDF, or image files\n• Create Excel templates from your description\n• Answer questions about your data\n\nType `/help` to see all commands, or describe what you need.',
    timestamp: new Date().toLocaleTimeString(),
  }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const { sessionId, plan, status, setSessionId, setStatus, addLog } = useAgentStore()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const addMsg = (msg: Omit<Message, 'id' | 'timestamp'>) => {
    setMessages(m => [...m, {
      ...msg,
      id: Date.now().toString(),
      timestamp: new Date().toLocaleTimeString(),
    }])
  }

  // ── File upload ─────────────────────────────────────────────────────────────
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff', '.webp'],
    },
    multiple: false,
    onDrop: async ([file]) => {
      if (!file) return
      addMsg({ role: 'user', text: `📎 Uploading: ${file.name}` })
      addLog({ timestamp: new Date().toLocaleTimeString(), agent: 'System', message: `File: ${file.name}`, level: 'info' })
      try {
        const upload = await uploadFile(file)
        setSessionId(upload.session_id)
        addMsg({
          role: 'agent',
          text: `File received: **${file.name}** (${upload.file_type.toUpperCase()})\n\nAnalyzing your data...`,
        })
        setStatus('running')
        await runAgent(upload.session_id)
      } catch (e: unknown) {
        addMsg({ role: 'agent', text: `Upload failed: ${(e as Error).message}` })
      }
    },
  })

  // ── Send message ────────────────────────────────────────────────────────────
  const handleSend = async (msg?: string) => {
    const text = (msg || input).trim()
    if (!text || loading) return
    setInput('')
    setLoading(true)

    addMsg({ role: 'user', text })

    try {
      // Special client-side handling
      if (text === '/approve' && sessionId) {
        await approveAll(sessionId)
        addMsg({ role: 'agent', text: 'All suggestions approved — generating your Excel file...' })
        setLoading(false)
        return
      }

      // Send to chat API
      const { data } = await axios.post(`${API}/api/chat/`, {
        session_id: sessionId,
        message: text,
      })

      addMsg({
        role: 'agent',
        text: data.text,
        action: data.action,
      })

      // Handle action triggers
      if (data.action?.trigger === 'run_pipeline' && sessionId) {
        setStatus('running')
        await runAgent(sessionId, text)
      }
      if (data.action?.trigger === 'approve_all' && sessionId) {
        await approveAll(sessionId)
      }

    } catch (e: unknown) {
      addMsg({ role: 'agent', text: `Something went wrong: ${(e as Error).message}` })
    } finally {
      setLoading(false)
    }
  }

  // ── WebSocket excel_ready event ─────────────────────────────────────────────
  // This is handled in useWebSocket.ts — it calls addExcelReadyMessage
  // which is exported below and called from the hook

  return (
    <div className="flex flex-col h-full bg-gray-950">

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">

        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}

        {/* Plan card */}
        {plan.length > 0 && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 mb-3">
            <p className="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wide flex items-center gap-1">
              <ChevronRight size={12} className="text-blue-400" /> Execution Plan
            </p>
            <ol className="space-y-1 mb-3">
              {plan.map((step, i) => (
                <li key={i} className="text-sm text-gray-300 flex gap-2">
                  <span className="text-blue-400 font-mono text-xs mt-0.5 shrink-0">{i + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
            {status === 'awaiting_approval' && sessionId && (
              <div className="flex gap-2">
                <button
                  onClick={() => { approveAll(sessionId); setStatus('approved') }}
                  className="flex items-center gap-1 text-xs bg-green-700 hover:bg-green-600 px-3 py-1.5 rounded-lg text-white font-medium"
                >
                  <CheckCheck size={12} /> Accept All & Generate Excel
                </button>
                <button className="text-xs text-gray-500 hover:text-white px-3 py-1.5 rounded-lg border border-gray-700">
                  Reject
                </button>
              </div>
            )}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-gray-500 mb-3">
            <Loader size={12} className="animate-spin" />
            SheetAgent is thinking...
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Quick prompts — shown when no session */}
      {!sessionId && (
        <div className="px-4 pb-2">
          <p className="text-xs text-gray-600 mb-2">Quick start:</p>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_PROMPTS.map(p => (
              <button
                key={p}
                onClick={() => handleSend(p)}
                className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-2.5 py-1 rounded-full border border-gray-700 transition-colors"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`mx-4 mb-2 border-2 border-dashed rounded-xl p-3 text-center cursor-pointer transition-all ${
          isDragActive
            ? 'border-blue-400 bg-blue-900/20 scale-[1.01]'
            : 'border-gray-800 hover:border-gray-600'
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
          <Upload size={13} />
          {isDragActive ? 'Drop file here' : 'Drop CSV, Excel, PDF or Image — or click to browse'}
        </div>
      </div>

      {/* Input bar */}
      <div className="px-4 pb-4 flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Describe your Excel needs, or type /help for commands..."
          disabled={loading}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 transition-colors"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          className="p-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-xl text-white transition-colors"
        >
          {loading ? <Loader size={15} className="animate-spin" /> : <Send size={15} />}
        </button>
      </div>
    </div>
  )
}
