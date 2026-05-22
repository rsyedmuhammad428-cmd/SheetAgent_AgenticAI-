import { useState } from 'react'
import { Search, TrendingUp } from 'lucide-react'
import axios from 'axios'
import { useAgentStore } from '../../store/agentStore'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface AnalyticsResult {
  question: string
  answer: string
}

const SAMPLE_QUESTIONS = [
  'What is the average revenue?',
  'Which column has the most missing values?',
  'What are the top 3 highest values?',
  'Are there any outliers?',
  'What is the total sum?',
]

export default function AnalyticsPanel() {
  const { sessionId } = useAgentStore()
  const [question, setQuestion] = useState('')
  const [results, setResults] = useState<AnalyticsResult[]>([])
  const [loading, setLoading] = useState(false)

  const ask = async (q: string) => {
    if (!sessionId || !q.trim()) return
    setLoading(true)
    try {
      const { data } = await axios.post(`${API}/api/p2/analytics`, {
        session_id: sessionId,
        question: q,
      })
      setResults(r => [{ question: data.question, answer: data.answer }, ...r])
      setQuestion('')
    } catch {
      setResults(r => [{ question: q, answer: 'Analysis failed. Please try again.' }, ...r])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 space-y-3">
      <p className="text-xs text-gray-400">Ask questions about your data in plain English.</p>

      {/* Sample questions */}
      <div className="flex flex-wrap gap-1">
        {SAMPLE_QUESTIONS.map(q => (
          <button
            key={q}
            onClick={() => ask(q)}
            className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-700"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && ask(question)}
          placeholder="Ask anything about your data..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={() => ask(question)}
          disabled={loading || !sessionId}
          className="p-2 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 rounded text-white"
        >
          {loading ? <span className="animate-spin text-xs">⟳</span> : <Search size={14} />}
        </button>
      </div>

      {/* Results */}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {results.map((r, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <p className="text-xs text-blue-400 mb-1 flex items-center gap-1">
              <TrendingUp size={10} /> {r.question}
            </p>
            <p className="text-xs text-gray-300 leading-relaxed">{r.answer}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
