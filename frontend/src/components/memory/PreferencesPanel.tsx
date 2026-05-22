import { useState } from 'react'
import { Save, RotateCcw } from 'lucide-react'
import { useMemoryStore } from '../../store/memoryStore'
import { useMemory } from '../../hooks/useMemory'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const THEMES = ['professional', 'minimal', 'colorful']
const CHART_STYLES = ['bar', 'line', 'pie']
const DATE_FORMATS = ['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY', 'DD-MMM-YYYY']
const CURRENCIES = ['USD', 'EUR', 'GBP', 'PKR', 'INR', 'AED', 'SAR']
const FONTS = ['Calibri', 'Arial', 'Times New Roman', 'Helvetica']

export default function PreferencesPanel() {
  const { preferences } = useMemoryStore()
  const { updatePref } = useMemory()
  const [saved, setSaved] = useState(false)

  if (!preferences) {
    return <div className="p-4 text-xs text-gray-500 animate-pulse">Loading preferences...</div>
  }

  const handleChange = (key: string, value: unknown) => {
    updatePref({ [key]: value })
    setSaved(false)
  }

  const handleReset = async () => {
    await axios.put(`${API}/api/memory/preferences/reset`)
    window.location.reload()
  }

  return (
    <div className="p-4 space-y-5 overflow-y-auto">

      {/* Excel */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Excel Output</h3>
        <div className="space-y-3">

          <div>
            <label className="text-xs text-gray-400 block mb-1">Theme</label>
            <div className="flex gap-1">
              {THEMES.map(t => (
                <button
                  key={t}
                  onClick={() => handleChange('excel_theme', t)}
                  className={`text-xs px-3 py-1 rounded border capitalize ${
                    preferences.excel_theme === t
                      ? 'bg-blue-700 border-blue-600 text-white'
                      : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Header Color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={`#${preferences.header_color}`}
                onChange={e => handleChange('header_color', e.target.value.replace('#', ''))}
                className="w-8 h-8 rounded cursor-pointer bg-transparent border-0"
              />
              <span className="text-xs font-mono text-gray-400">#{preferences.header_color}</span>
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Font</label>
            <select
              value={preferences.font_name}
              onChange={e => handleChange('font_name', e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 focus:outline-none"
            >
              {FONTS.map(f => <option key={f}>{f}</option>)}
            </select>
          </div>

          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={preferences.freeze_header}
                onChange={e => handleChange('freeze_header', e.target.checked)}
                className="accent-blue-500"
              />
              <span className="text-xs text-gray-300">Freeze header</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={preferences.auto_filter}
                onChange={e => handleChange('auto_filter', e.target.checked)}
                className="accent-blue-500"
              />
              <span className="text-xs text-gray-300">Auto filter</span>
            </label>
          </div>
        </div>
      </section>

      {/* Data format */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Data Format</h3>
        <div className="space-y-3">

          <div>
            <label className="text-xs text-gray-400 block mb-1">Date Format</label>
            <div className="flex flex-wrap gap-1">
              {DATE_FORMATS.map(f => (
                <button
                  key={f}
                  onClick={() => handleChange('date_format', f)}
                  className={`text-xs px-2 py-1 rounded border font-mono ${
                    preferences.date_format === f
                      ? 'bg-blue-700 border-blue-600 text-white'
                      : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Currency</label>
            <div className="flex flex-wrap gap-1">
              {CURRENCIES.map(c => (
                <button
                  key={c}
                  onClick={() => handleChange('currency', c)}
                  className={`text-xs px-2 py-1 rounded border ${
                    preferences.currency === c
                      ? 'bg-blue-700 border-blue-600 text-white'
                      : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Charts */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Charts</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Default Chart Type</label>
            <div className="flex gap-1">
              {CHART_STYLES.map(s => (
                <button
                  key={s}
                  onClick={() => handleChange('chart_style', s)}
                  className={`text-xs px-3 py-1 rounded border capitalize ${
                    preferences.chart_style === s
                      ? 'bg-blue-700 border-blue-600 text-white'
                      : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={preferences.always_generate_charts}
              onChange={e => handleChange('always_generate_charts', e.target.checked)}
              className="accent-blue-500"
            />
            <span className="text-xs text-gray-300">Always generate charts automatically</span>
          </label>
        </div>
      </section>

      {/* Workflow */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Workflow</h3>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={preferences.auto_approve_cleaning}
            onChange={e => handleChange('auto_approve_cleaning', e.target.checked)}
            className="accent-blue-500"
          />
          <span className="text-xs text-gray-300">Auto-approve cleaning suggestions</span>
        </label>
      </section>

      {/* Reset */}
      <button
        onClick={handleReset}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-400 border border-gray-700 hover:border-red-800 px-3 py-1.5 rounded"
      >
        <RotateCcw size={11} /> Reset to defaults
      </button>
    </div>
  )
}
