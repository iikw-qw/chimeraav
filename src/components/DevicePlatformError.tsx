import { AlertTriangle, RefreshCw, Plug, X } from 'lucide-react'
import { Button } from './ui'

interface DevicePlatformErrorProps {
  error: { error: string; message: string; instructions: string[] }
  onRefresh?: () => void
  onConnect?: () => void
  onDismiss?: () => void
}

export function DevicePlatformError({ error, onRefresh, onConnect, onDismiss }: DevicePlatformErrorProps) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-5">
      <div className="flex items-center gap-2 text-red-400">
        <AlertTriangle className="h-5 w-5" />
        <h3 className="text-sm font-semibold">{error.message}</h3>
      </div>
      <ol className="mt-3 list-inside list-decimal space-y-1 text-xs text-[--txt-2]">
        {error.instructions.map((inst, i) => (
          <li key={i}>{inst}</li>
        ))}
      </ol>
      <div className="mt-4 flex gap-2">
        {onRefresh && (
          <Button variant="secondary" size="sm" onClick={onRefresh} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
            Refresh Devices
          </Button>
        )}
        {onConnect && (
          <Button variant="secondary" size="sm" onClick={onConnect} leftIcon={<Plug className="h-3.5 w-3.5" />}>
            Connect Device
          </Button>
        )}
        {onDismiss && (
          <Button variant="ghost" size="sm" onClick={onDismiss} leftIcon={<X className="h-3.5 w-3.5" />}>
            Dismiss
          </Button>
        )}
      </div>
    </div>
  )
}
