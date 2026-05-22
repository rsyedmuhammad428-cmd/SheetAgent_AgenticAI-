import { useEffect, useRef } from 'react'
import { useAgentStore } from '../store/agentStore'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

// Global callback — set by ChatPanel to inject download messages
let onExcelReady: ((data: unknown) => void) | null = null
export function setExcelReadyCallback(cb: (data: unknown) => void) {
  onExcelReady = cb
}

export function useWebSocket(sessionId: string | null) {
  const ws = useRef<WebSocket | null>(null)
  const { addLog, setStatus, setSuggestions, setPlan, setOutputPath, setReflectionReport } = useAgentStore()

  useEffect(() => {
    if (!sessionId) return

    const url = `${WS_BASE}/${sessionId}`
    ws.current = new WebSocket(url)

    ws.current.onopen = () => {
      addLog({ timestamp: new Date().toLocaleTimeString(), agent: 'System', message: 'Connected', level: 'info' })
    }

    ws.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        switch (msg.type) {
          case 'log':
            addLog({
              timestamp: msg.data.timestamp,
              agent: msg.data.agent,
              message: msg.data.message,
              level: msg.data.level || 'info',
            })
            break
          case 'status':
            setStatus(msg.data.status)
            break
          case 'suggestion':
            setSuggestions(msg.data.suggestions)
            break
          case 'complete':
            setStatus('complete')
            if (msg.data?.output_path) setOutputPath(msg.data.output_path)
            break
          case 'reflection':
            setReflectionReport(msg.data)
            break
          case 'excel_ready':
            // Notify ChatPanel to add a download message
            if (onExcelReady) onExcelReady(msg.data)
            setStatus('complete')
            break
        }
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }

    ws.current.onerror = () => {
      addLog({
        timestamp: new Date().toLocaleTimeString(),
        agent: 'System',
        message: 'WebSocket error — retrying...',
        level: 'error',
      })
    }

    ws.current.onclose = () => {
      addLog({
        timestamp: new Date().toLocaleTimeString(),
        agent: 'System',
        message: 'WebSocket disconnected',
        level: 'warning',
      })
    }

    const ping = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send('ping')
      }
    }, 25000)

    return () => {
      clearInterval(ping)
      ws.current?.close()
    }
  }, [sessionId])
}
