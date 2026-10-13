import { useEffect, useState } from 'react'
import { CheckCircle, AlertTriangle, Loader2, RefreshCw, X, Wrench } from 'lucide-react'
import { Button } from './ui'
import { api } from '../api/client'

interface TroubleshootResult {
  adb_installed: boolean
  adb_version: string
  devices: { serial: string; state: string }[]
  suggestions: string[]
}

interface Props {
  onClose: () => void
}

export function Troubleshooter({ onClose }: Props) {
  const [data, setData] = useState<TroubleshootResult | null>(null)
  const [loading, setLoading] = useState(true)

  const run = async () => {
    setLoading(true)
    try {
      const res = await api.post('/api/v1/devices/troubleshoot')
      setData(res.data as TroubleshootResult)
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { run() }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-md rounded-xl border border-[--line-1] bg-[--bg-1] shadow-2xl">
        <div className="flex items-center gap-3 border-b border-[--line-1] px-6 py-4">
          <Wrench className="h-5 w-5 text-blue-400" />
          <h2 className="text-sm font-semibold text-[--txt-1]">Device Troubleshooter</h2>
          <button type="button" onClick={onClose} className="ml-auto rounded-md p-1 text-[--txt-3] hover:bg-[--bg-2]">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-8">
              <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
              <span className="text-xs text-[--txt-3]">Running diagnostics...</span>
            </div>
          ) : data ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs">
                {data.adb_installed
                  ? <CheckCircle className="h-4 w-4 text-emerald-400" />
                  : <AlertTriangle className="h-4 w-4 text-red-400" />}
                <span className="text-[--txt-1]">ADB: {data.adb_installed ? `installed (v${data.adb_version})` : 'NOT installed'}</span>
              </div>

              <div className="text-xs text-[--txt-2]">
                Devices found: {data.devices.length}
              </div>

              {data.devices.map((d, i) => (
                <div key={i} className="ml-4 flex items-center gap-2 text-xs">
                  {d.state === 'device'
                    ? <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                    : <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />}
                  <span className="text-[--txt-2]">{d.serial}: {d.state}</span>
                </div>
              ))}

              {data.suggestions.length > 0 && (
                <div className="rounded-lg bg-amber-500/10 p-3">
                  <p className="mb-1 text-[10px] font-medium text-amber-400">Suggestions:</p>
                  {data.suggestions.map((s, i) => (
                    <p key={i} className="text-[10px] text-amber-300">&rarr; {s}</p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="py-8 text-center text-xs text-red-400">Failed to run diagnostics</p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[--line-1] px-6 py-3">
          <Button variant="secondary" size="sm" onClick={run} disabled={loading} leftIcon={<RefreshCw className="h-3 w-3" />}>
            Run Again
          </Button>
          <Button variant="primary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}
