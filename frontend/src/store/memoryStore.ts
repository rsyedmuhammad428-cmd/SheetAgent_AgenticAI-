import { create } from 'zustand'

export interface UserPreferences {
  date_format: string
  currency: string
  currency_symbol: string
  excel_theme: string
  header_color: string
  font_name: string
  font_size: number
  freeze_header: boolean
  auto_filter: boolean
  chart_style: string
  always_generate_charts: boolean
  auto_approve_cleaning: boolean
}

export interface SessionSummary {
  session_id: string
  file_name: string
  file_type: string
  schema_type: string
  row_count: number
  col_count: number
  status: string
  quality_score: number | null
  created_at: string
}

export interface MemorySnippet {
  key: string
  value: string
  confidence: number
}

interface MemoryStore {
  preferences: UserPreferences | null
  recentSessions: SessionSummary[]
  snippets: MemorySnippet[]
  loaded: boolean

  setPreferences: (p: UserPreferences) => void
  setRecentSessions: (s: SessionSummary[]) => void
  setSnippets: (s: MemorySnippet[]) => void
  setLoaded: (v: boolean) => void
  updatePreference: (key: keyof UserPreferences, value: unknown) => void
}

export const useMemoryStore = create<MemoryStore>((set) => ({
  preferences: null,
  recentSessions: [],
  snippets: [],
  loaded: false,

  setPreferences: (preferences) => set({ preferences }),
  setRecentSessions: (recentSessions) => set({ recentSessions }),
  setSnippets: (snippets) => set({ snippets }),
  setLoaded: (loaded) => set({ loaded }),
  updatePreference: (key, value) =>
    set((s) => ({
      preferences: s.preferences ? { ...s.preferences, [key]: value } : s.preferences,
    })),
}))
