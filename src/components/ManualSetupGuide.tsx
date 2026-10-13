import { useState } from 'react'
import { BookOpen, CheckCircle, Plug, RefreshCw, Search, X, Wrench } from 'lucide-react'
import { Button } from './ui'
import { api } from '../api/client'
import { toast } from '../hooks/useToast'

interface Props {
  serial?: string | null
  onClose: () => void
  onCheckConnection?: () => void
  onDetectApps?: () => void
}

export function ManualSetupGuide({ serial, onClose, onCheckConnection, onDetectApps }: Props) {
  const [showTroubleshooter, setShowTroubleshooter] = useState(false)
  const [troubleshootData, setTroubleshootData] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const runTroubleshoot = async () => {
    setLoading(true)
    try {
      const res = await api.post('/api/v1/devices/troubleshoot')
      setTroubleshootData(res.data)
      setShowTroubleshooter(true)
    } catch {
      toast.danger('Troubleshooter failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-xl border border-[--line-1] bg-[--bg-1] shadow-2xl">
        <div className="flex items-center gap-3 border-b border-[--line-1] px-6 py-4">
          <BookOpen className="h-5 w-5 text-amber-400" />
          <div>
            <h2 className="text-sm font-semibold text-[--txt-1]">Manual Setup Guide</h2>
            <p className="text-[10px] text-[--txt-3]">Auto-setup couldn't complete. Follow these steps:</p>
          </div>
          <button type="button" onClick={onClose} className="ml-auto rounded-md p-1 text-[--txt-3] hover:bg-[--bg-2]">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[60vh] space-y-4 overflow-y-auto px-6 py-4">
          {/* Step 1 */}
          <div className="rounded-lg bg-[--bg-2] p-3">
            <h3 className="mb-2 text-xs font-semibold text-[--txt-1]">1. ON YOUR PHONE:</h3>
            <ol className="list-inside list-decimal space-y-1 text-[10px] text-[--txt-2]">
              <li>Go to Settings &rarr; About Phone</li>
              <li>Tap "Build Number" 7 times</li>
              <li>Go back &rarr; Developer Options</li>
              <li>Enable "USB Debugging"</li>
              <li>Connect USB cable to computer</li>
              <li>Tap "Allow" on the debugging prompt</li>
            </ol>
          </div>

          {/* Step 2 */}
          <div className="rounded-lg bg-[--bg-2] p-3">
            <h3 className="mb-2 text-xs font-semibold text-[--txt-1]">2. INSTALL SOCIAL APPS:</h3>
            <ul className="list-inside list-disc space-y-1 text-[10px] text-[--txt-2]">
              <li>Open Google Play Store on phone</li>
              <li>Install: Instagram, TikTok, Threads</li>
            </ul>
          </div>

          {/* Step 3 */}
          <div className="rounded-lg bg-[--bg-2] p-3">
            <h3 className="mb-2 text-xs font-semibold text-[--txt-1]">3. IN THIS APP:</h3>
            <ul className="list-inside list-disc space-y-1 text-[10px] text-[--txt-2]">
              <li>Click "Check Connection" below</li>
              <li>Click "Detect Apps"</li>
              <li>If everything shows a green check — you're ready</li>
            </ul>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            {onCheckConnection && (
              <Button variant="secondary" size="sm" onClick={onCheckConnection} leftIcon={<Plug className="h-3 w-3" />}>
                Check Connection
              </Button>
            )}
            {onDetectApps && (
              <Button variant="secondary" size="sm" onClick={onDetectApps} leftIcon={<Search className="h-3 w-3" />}>
                Detect Apps
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={onClose}>
              Close Guide
            </Button>
          </div>

          {/* Troubleshooting */}
          <div className="border-t border-[--line-1] pt-3">
            <p className="mb-2 text-[10px] font-medium text-[--txt-3]">Still not working?</p>
            <ul className="mb-3 list-inside list-disc space-y-1 text-[10px] text-[--txt-3]">
              <li>Try a different USB cable</li>
              <li>Try a different USB port</li>
              <li>Restart your phone</li>
              <li>Restart this application</li>
              <li>Check that ADB drivers are installed (Windows)</li>
            </ul>
            <Button
              variant="secondary"
              size="sm"
              onClick={runTroubleshoot}
              disabled={loading}
              leftIcon={<Wrench className="h-3 w-3" />}
            >
              {loading ? 'Running...' : 'Open Troubleshooter'}
            </Button>
          </div>

          {/* Troubleshooter results */}
          {showTroubleshooter && troubleshootData && (
            <div className="rounded-lg border border-[--line-1] bg-[--bg-2] p-3">
              <h3 className="mb-2 text-xs font-semibold text-[--txt-1]">Diagnostics</h3>
              <div className="space-y-1 text-[10px]">
                <div className="flex items-center gap-2">
                  {troubleshootData.adb_installed
                    ? <CheckCircle className="h-3 w-3 text-emerald-400" />
                    : <X className="h-3 w-3 text-red-400" />}
                  <span className="text-[--txt-2]">ADB: {troubleshootData.adb_installed ? `installed (v${troubleshootData.adb_version})` : 'NOT installed'}</span>
                </div>
                <div className="text-[--txt-2]">
                  Devices found: {troubleshootData.devices?.length ?? 0}
                </div>
                {troubleshootData.devices?.map((d: any, i: number) => (
                  <div key={i} className="ml-4 text-[--txt-3]">
                    {d.serial}: {d.state === 'device' ? '✅ connected' : `⚠️ ${d.state}`}
                  </div>
                ))}
                {troubleshootData.suggestions?.length > 0 && (
                  <div className="mt-2">
                    <p className="font-medium text-amber-400">Suggestions:</p>
                    {troubleshootData.suggestions.map((s: string, i: number) => (
                      <p key={i} className="ml-2 text-[--txt-2]">&rarr; {s}</p>
                    ))}
                  </div>
                )}
              </div>
              <Button variant="ghost" size="sm" onClick={runTroubleshoot} className="mt-2" leftIcon={<RefreshCw className="h-3 w-3" />}>
                Run Again
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
