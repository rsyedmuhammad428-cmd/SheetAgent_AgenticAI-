import { Folder, FileSpreadsheet, FileText, Image } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { listWorkspace } from '../../api/client'

const FOLDERS = ['incoming', 'processing', 'extracted', 'cleaned', 'excels', 'charts', 'reports']

export default function Sidebar() {
  const { data } = useQuery({ queryKey: ['workspace'], queryFn: listWorkspace, refetchInterval: 3000 })

  return (
    <aside className="w-52 border-r border-gray-800 bg-gray-950 flex flex-col">
      <div className="px-3 py-3 border-b border-gray-800">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Workspace</span>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        {FOLDERS.map(folder => {
          const listing = data?.[folder]
          const count = listing?.items?.length || 0
          return (
            <div key={folder} className="px-2">
              <div className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-800 cursor-pointer group">
                <Folder size={13} className="text-blue-400 shrink-0" />
                <span className="text-xs text-gray-300 flex-1 capitalize">{folder}</span>
                {count > 0 && (
                  <span className="text-xs text-gray-500">{count}</span>
                )}
              </div>
              {listing?.items?.slice(0, 5).map(item => (
                <div key={item.path} className="flex items-center gap-2 pl-6 pr-2 py-1 hover:bg-gray-800/50 cursor-pointer rounded">
                  {item.name.endsWith('.xlsx') ? <FileSpreadsheet size={11} className="text-green-400" /> : <FileText size={11} className="text-gray-500" />}
                  <span className="text-xs text-gray-500 truncate">{item.name}</span>
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </aside>
  )
}
