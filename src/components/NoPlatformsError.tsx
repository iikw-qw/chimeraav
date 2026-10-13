import { AlertTriangle, RefreshCw, Plug, X } from 'lucide-react'
import { Button } from './ui'

interface NoPlatformsErrorProps {
  serial: string
  onRetry: () => void
  onConnect: () => void
  onDismiss?: () => void
}

export function NoPlatformsError({ serial, onRetry, onConnect, onDismiss }: NoPlatformsErrorProps) {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5">
      <div className="flex items-center gap-2 text-amber-400">
        <AlertTriangle className="h-5 w-5" />
        <h3 className="text-sm font-semibold">No installed platforms detected</h3>
      </div>
      <ol className="mt-3 list-inside list-decimal space-y-1 text-xs text-[--txt-2]">
        <li>Connect your device via Chimera Agent</li>
        <li>Install social media apps (Instagram, TikTok, etc.)</li>
        <li>Click "Detect Platforms" to refresh</li>
        <li>Ensure USB Debugging is enabled</li>
        <li>Try restarting the agent</li>
      </ol>
      <div className="mt-4 flex gap-2">
        <Button variant="secondary" size="sm" onClick={onRetry} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
          Detect Again
        </Button>
        <Button variant="secondary" size="sm" onClick={onConnect} leftIcon={<Plug className="h-3.5 w-3.5" />}>
          Connect Device
        </Button>
        {onDismiss && (
          <Button variant="ghost" size="sm" onClick={onDismiss} leftIcon={<X className="h-3.5 w-3.5" />}>
            Dismiss
          </Button>
        )}
      </div>
    </div>
  )
}
