import { useState } from 'react'
import { Plus, Trash2, Zap } from 'lucide-react'
import axios from 'axios'
import { useAgentStore } from '../../store/agentStore'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const FORMULA_SUGGESTIONS = [
  'Sum of revenue column',
  'Average order value',
  'Count total records',
  'Calculate profit margin',
  'Show maximum sales',
  'Running total',
  'If profit > 1000 then High else Low',
]

export default function FormulaPanel() {
  const { sessionId, addLog } = useAgentStore()
  const [formulas, setFormulas] = useState<string[]>([''])
  const [loading, setLoading] = useState(false)
  const [applied, setApplied] = useState(false)

  const updateFormula = (i: number, val: string) => {
    setFormulas(f => f.map((v, idx) => idx === i ? val : v))
  }

  const addFormula = () => setFormulas(f => [...f, ''])
  const removeFormula = (i: number) => setFormulas(f => f.filter((_, idx) => idx !== i))

  const handleApply = async () => {
    if (!sessionId) return
    const valid = formulas.filter(f => f.trim())
    if (!valid.length) return
    setLoading(true)
    try {
      await axios.post(`${API}/api/p2/formula`, {
        session_id: sessionId,
        formulas: valid,
      })
      setApplied(true)
      addLog({ timestamp: new Date().toLocaleTimeString(), agent: 'FormulaAgent', message: `${valid.length} formula(s) queued`, level: 'info' })
    } catch (e) {
      addLog({ timestamp: new Date().toLocaleTimeString(), agent: 'FormulaAgent', message: 'Formula request failed', level: 'error' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 space-y-3">
      <p className="text-xs text-gray-400">
        Describe formulas in plain English — Gemini will convert them to Excel formulas.
      </p>

      {/* Quick suggestions */}
      <div className="flex flex-wrap gap-1">
        {FORMULA_SUGGESTIONS.map(s => (
          <button
            key={s}
            onClick={() => setFormulas(f => [...f.filter(x => x), s])}
            className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-700"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Formula inputs */}
      <div className="space-y-2">
        {formulas.map((f, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={f}
              onChange={e => updateFormula(i, e.target.value)}
              placeholder={`e.g. "sum of sales column"`}
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            {formulas.length > 1 && (
              <button onClick={() => removeFormula(i)} className="text-gray-600 hover:text-red-400">
                <Trash2 size={14} />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <button onClick={addFormula} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white border border-gray-700 px-2 py-1 rounded">
          <Plus size={12} /> Add formula
        </button>
        <button
          onClick={handleApply}
          disabled={loading || applied || !sessionId}
          className="flex items-center gap-1 text-xs bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white px-3 py-1 rounded"
        >
          <Zap size={12} />
          {loading ? 'Applying...' : applied ? 'Applied ✓' : 'Apply to Excel'}
        </button>
      </div>
    </div>
  )
}
