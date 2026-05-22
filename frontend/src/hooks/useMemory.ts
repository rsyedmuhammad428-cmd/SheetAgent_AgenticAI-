import { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useMemoryStore } from '../store/memoryStore'

const API = import.meta.env.VITE_API_URL || ''

export function useMemory() {
  const { setPreferences, setRecentSessions, setSnippets, setLoaded } = useMemoryStore()
  const queryClient = useQueryClient()

  // Load full context on mount
  const { data, isLoading } = useQuery({
    queryKey: ['memory-context'],
    queryFn: async () => {
      const { data } = await axios.get(`${API}/api/memory/context`)
      return data
    },
    staleTime: 30_000,
  })

  useEffect(() => {
    if (data) {
      setPreferences(data.preferences)
      setRecentSessions(data.recent_sessions)
      setSnippets(data.snippets)
      setLoaded(true)
    }
  }, [data])

  // Update a single preference
  const updatePref = useMutation({
    mutationFn: async (updates: Record<string, unknown>) => {
      const { data } = await axios.patch(`${API}/api/memory/preferences`, { updates })
      return data
    },
    onSuccess: (data) => {
      setPreferences(data)
      queryClient.invalidateQueries({ queryKey: ['memory-context'] })
    },
  })

  // Clear all memory
  const clearMemory = useMutation({
    mutationFn: async () => {
      await axios.delete(`${API}/api/memory/snippets`)
    },
    onSuccess: () => {
      setSnippets([])
      queryClient.invalidateQueries({ queryKey: ['memory-context'] })
    },
  })

  return {
    isLoading,
    updatePref: updatePref.mutate,
    clearMemory: clearMemory.mutate,
  }
}
