import { create } from 'zustand'

export type AgentStatus =
  | 'idle' | 'running' | 'awaiting_approval'
  | 'approved' | 'complete' | 'error'

export interface Suggestion {
  id: string
  title: string
  description: string
  action: string
  data?: Record<string, unknown>
  approved?: boolean
}

export interface LogEntry {
  timestamp: string
  agent: string
  message: string
  level: 'info' | 'warning' | 'error'
}

export interface ReflectionReport {
  passed: string[]
  warnings: string[]
  errors: string[]
  score: number
  recommendation: string
}

interface AgentStore {
  sessionId: string | null
  status: AgentStatus
  plan: string[]
  suggestions: Suggestion[]
  logs: LogEntry[]
  schemaType: string | null
  outputPath: string | null
  error: string | null
  reflectionReport: ReflectionReport | null  // Phase 2
  fileType: string | null                    // Phase 3

  setSessionId: (id: string) => void
  setStatus: (s: AgentStatus) => void
  setPlan: (p: string[]) => void
  setSuggestions: (s: Suggestion[]) => void
  addLog: (entry: LogEntry) => void
  setSchemaType: (t: string) => void
  setOutputPath: (p: string) => void
  setError: (e: string | null) => void
  setReflectionReport: (r: ReflectionReport) => void  // Phase 2
  setFileType: (t: string | null) => void             // Phase 3
  reset: () => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  sessionId: null,
  status: 'idle',
  plan: [],
  suggestions: [],
  logs: [],
  schemaType: null,
  outputPath: null,
  error: null,
  reflectionReport: null,
  fileType: null,

  setSessionId: (id) => set({ sessionId: id }),
  setStatus: (status) => set({ status }),
  setPlan: (plan) => set({ plan }),
  setSuggestions: (suggestions) => set({ suggestions }),
  addLog: (entry) => set((s) => ({ logs: [...s.logs.slice(-200), entry] })),
  setSchemaType: (schemaType) => set({ schemaType }),
  setOutputPath: (outputPath) => set({ outputPath }),
  setError: (error) => set({ error }),
  setReflectionReport: (reflectionReport) => set({ reflectionReport }),
  setFileType: (fileType) => set({ fileType }),
  reset: () => set({
    sessionId: null, status: 'idle', plan: [], suggestions: [],
    logs: [], schemaType: null, outputPath: null, error: null, reflectionReport: null,
    fileType: null,
  }),
}))
