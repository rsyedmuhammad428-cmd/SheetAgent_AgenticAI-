import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
})

export interface UploadResponse {
  session_id: string
  file_name: string
  file_type: string
  file_path: string
  message: string
}

export interface AgentStateResponse {
  session_id: string
  status: string
  plan: string[]
  suggestions: Suggestion[]
  execution_steps: LogEntry[]
  schema_type?: string
  output_excel_path?: string
  error?: string
}

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
  level: string
}

export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/api/upload/', form)
  return data
}

export const runAgent = async (sessionId: string, userMessage?: string): Promise<AgentStateResponse> => {
  const { data } = await api.post('/api/agent/run', {
    session_id: sessionId,
    user_message: userMessage,
  })
  return data
}

export const approveAll = async (sessionId: string): Promise<AgentStateResponse> => {
  const { data } = await api.post(`/api/agent/approve-all?session_id=${sessionId}`)
  return data
}

export const approveSuggestion = async (sessionId: string, suggestionId: string, approved: boolean) => {
  const { data } = await api.post('/api/agent/approve', {
    session_id: sessionId,
    suggestion_id: suggestionId,
    approved,
  })
  return data
}

export const getAgentState = async (sessionId: string): Promise<AgentStateResponse> => {
  const { data } = await api.get(`/api/agent/${sessionId}/state`)
  return data
}

export const listWorkspace = async () => {
  const { data } = await api.get('/api/workspace/')
  return data
}
