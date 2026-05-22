import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { FileSearch, Scan, CheckCircle, AlertTriangle } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface OCRStatus {
  session_id: string
  file_type: string
  is_searchable: boolean | null
  page_count: number | null
  rows_extracted: number
  status: string
}

export default function OCRStatusCard({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useQuery<OCRStatus>({
    queryKey: ['ocr-status', sessionId],
    queryFn: async () => {
      const { data } = await axios.get(`${API}/api/ocr/status/${sessionId}`)
      return data
    },
    enabled: !!sessionId,
    refetchInterval: 2000,
  })

  if (isLoading || !data) return null
  if (!['pdf', 'image'].includes(data.file_type)) return null

  const isPDF = data.file_type === 'pdf'

  return (
    <div className="mx-4 mb-3 bg-gray-900 border border-gray-700 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2">
        {isPDF ? <FileSearch size={14} className="text-blue-400" /> : <Scan size={14} className="text-blue-400" />}
        <span className="text-xs font-semibold text-gray-300">OCR Pipeline</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {isPDF && (
          <div className="text-center">
            <div className="text-sm font-bold text-white">{data.page_count ?? '—'}</div>
            <div className="text-xs text-gray-500">Pages</div>
          </div>
        )}
        <div className="text-center">
          <div className="text-sm font-bold text-white">{data.rows_extracted}</div>
          <div className="text-xs text-gray-500">Rows extracted</div>
        </div>
        {isPDF && data.is_searchable !== null && (
          <div className="text-center">
            <div className="flex justify-center">
              {data.is_searchable
                ? <CheckCircle size={16} className="text-green-400" />
                : <AlertTriangle size={16} className="text-amber-400" />}
            </div>
            <div className="text-xs text-gray-500">
              {data.is_searchable ? 'Searchable' : 'Scanned'}
            </div>
          </div>
        )}
      </div>

      {isPDF && !data.is_searchable && (
        <p className="text-xs text-amber-400 mt-2">
          Scanned PDF detected — using EasyOCR + img2table pipeline
        </p>
      )}
      {isPDF && data.is_searchable && (
        <p className="text-xs text-green-400 mt-2">
          Searchable PDF — using pdfplumber for fast table extraction
        </p>
      )}
    </div>
  )
}
