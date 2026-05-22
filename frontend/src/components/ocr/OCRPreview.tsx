import { useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Eye, Loader } from 'lucide-react'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface PreviewRow {
  [key: string]: string
}

export default function OCRPreview() {
  const [rows, setRows] = useState<PreviewRow[]>([])
  const [loading, setLoading] = useState(false)
  const [engine, setEngine] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff', '.webp'],
    },
    multiple: false,
    onDrop: async ([file]) => {
      if (!file) return
      setLoading(true)
      setRows([])
      setError(null)
      const form = new FormData()
      form.append('file', file)
      try {
        const { data } = await axios.post(`${API}/api/ocr/preview`, form)
        setRows(data.rows || [])
        setEngine(data.engine || null)
        if (data.message) setError(data.message)
      } catch (e: unknown) {
        setError('Preview failed — try full processing instead')
      } finally {
        setLoading(false)
      }
    },
  })

  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <div className="p-4 space-y-3">
      <p className="text-xs text-gray-400">
        Drop a PDF or image for a quick OCR preview (first 10 rows, no session created).
      </p>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-blue-400 bg-blue-900/20' : 'border-gray-700 hover:border-gray-500'
        }`}
      >
        <input {...getInputProps()} />
        <Eye size={16} className="mx-auto mb-1 text-gray-500" />
        <p className="text-xs text-gray-500">
          {isDragActive ? 'Drop to preview' : 'Drop PDF or image here'}
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Loader size={12} className="animate-spin" />
          Running OCR preview...
        </div>
      )}

      {error && <p className="text-xs text-amber-400">{error}</p>}

      {engine && (
        <p className="text-xs text-gray-500">Engine: <span className="text-blue-400">{engine}</span></p>
      )}

      {rows.length > 0 && (
        <div className="overflow-auto max-h-60 rounded border border-gray-800">
          <table className="w-full text-xs">
            <thead className="bg-gray-900 sticky top-0">
              <tr>
                {columns.map(col => (
                  <th key={col} className="px-2 py-1.5 text-left text-gray-400 border-b border-gray-800 whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-gray-950' : 'bg-gray-900'}>
                  {columns.map(col => (
                    <td key={col} className="px-2 py-1 text-gray-300 border-b border-gray-800/50 max-w-[150px] truncate">
                      {row[col] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
