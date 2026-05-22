import { CheckCircle, AlertTriangle, XCircle, RefreshCw } from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'

export default function ReflectionPanel() {
  const { reflectionReport } = useAgentStore()

  if (!reflectionReport) {
    return (
      <div className="p-4 text-xs text-gray-500 flex items-center gap-2">
        <RefreshCw size={12} className="animate-spin" />
        Reflection report will appear after Excel generation.
      </div>
    )
  }

  const { passed = [], warnings = [], errors = [], score = 0, recommendation = '' } = reflectionReport

  const scoreColor = score >= 0.8 ? 'text-green-400' : score >= 0.5 ? 'text-amber-400' : 'text-red-400'
  const scoreBar = score >= 0.8 ? 'bg-green-500' : score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="p-4 space-y-3">
      {/* Score */}
      <div className="flex items-center gap-3">
        <span className={`text-3xl font-bold ${scoreColor}`}>{Math.round(score * 100)}%</span>
        <div className="flex-1">
          <div className="text-xs text-gray-400 mb-1">Quality Score</div>
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div className={`h-full ${scoreBar} rounded-full transition-all`} style={{ width: `${score * 100}%` }} />
          </div>
        </div>
      </div>

      {/* Recommendation */}
      {recommendation && (
        <p className="text-xs text-gray-300 bg-gray-900 rounded p-2 border-l-2 border-blue-500">
          {recommendation}
        </p>
      )}

      {/* Passed checks */}
      {passed.map((item: string, i: number) => (
        <div key={i} className="flex items-start gap-2 text-xs text-green-300">
          <CheckCircle size={12} className="mt-0.5 shrink-0 text-green-500" />
          {item}
        </div>
      ))}

      {/* Warnings */}
      {warnings.map((item: string, i: number) => (
        <div key={i} className="flex items-start gap-2 text-xs text-amber-300">
          <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-500" />
          {item}
        </div>
      ))}

      {/* Errors */}
      {errors.map((item: string, i: number) => (
        <div key={i} className="flex items-start gap-2 text-xs text-red-300">
          <XCircle size={12} className="mt-0.5 shrink-0 text-red-500" />
          {item}
        </div>
      ))}
    </div>
  )
}
