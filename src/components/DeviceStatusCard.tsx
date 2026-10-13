import { useEffect, useState } from 'react'
import {
  Camera,
  CalendarClock,
  Flame,
  MessageSquare,
  Smartphone,
  Wrench,
} from 'lucide-react'
import { Button } from './ui'
import { api } from '../api/client'
import { cn } from '../lib/cn'

interface PlatformStatus {
  name: string
  package?: string
  installed: boolean
  version?: string
}

interface DeviceFullStatus {
  serial: string
  model: string
  android_version: string
  online: boolean
  agent: { installed: boolean; version: string; running: boolean }
  accessibility: { enabled: boolean }
  platforms: PlatformStatus[]
  last_activity: string | null
  warmup_count: number
  battery_percent: number
}

interface Props {
  serial: string
  name: string
  onFixEverything: () => void
  onWarmup?: () => void
  onSchedule?: () => void
  onScreenshot?: () => void
  onScanDms?: () => void
}

const PLATFORM_ICONS: Record<string, string> = {
  instagram: '📸', tiktok: '🎵', threads: '💬',
  twitter: '🐦', facebook: '📱', youtube: '▶️', linkedin: '💼',
}

export function DeviceStatusCard({ serial, name, onFixEverything, onWarmup, onSchedule, onScreenshot, onScanDms }: Props) {
  const [status, setStatus] = useState<DeviceFullStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchStatus = () => {
    setLoading(true)
    api.get(`/api/v1/devices/${serial}/full-status`)
      .then((r) => setStatus(r.data as DeviceFullStatus))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30_000)
    return () => clearInterval(interval)
  }, [serial])

  if (loading && !status) {
    return (
      <div className="rounded-xl border border-[--line-1] bg-[--bg-1] p-4">
        <div className="flex items-center gap-2 text-xs text-[--txt-3]">
          <Smartphone className="h-4 w-4 animate-pulse" />
          Loading {name}...
        </div>
      </div>
    )
  }

  if (!status) return null

  const hasIssues = !status.agent.installed || !status.accessibility.enabled ||
    status.platforms.filter((p) => p.installed).length === 0

  const allGood = status.agent.installed && status.accessibility.enabled &&
    status.platforms.filter((p) => p.installed).length > 0

  return (
    <div className={cn(
      'rounded-xl border bg-[--bg-1] transition-all',
      allGood ? 'border-emerald-500/30' : 'border-[--line-1]',
    )}>
      {/* Header */}
      <div className="border-b border-[--line-1] px-4 py-3">
        <div className="flex items-center gap-2">
          <Smartphone className="h-4 w-4 text-[--txt-2]" />
          <span className="text-sm font-medium text-[--txt-1]">{name}</span>
          {status.battery_percent > 0 && (
            <span className={cn(
              'ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium',
              status.battery_percent > 20 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400',
            )}>
              {status.battery_percent}%
            </span>
          )}
        </div>
        <div className="mt-0.5 text-[10px] text-[--txt-3]">
          {status.model} &middot; Android {status.android_version}
        </div>
      </div>

      {/* Status rows */}
      <div className="space-y-1 px-4 py-3">
        <StatusRow label="Connection" ok={status.online} text={status.online ? 'Online' : 'Offline'} />
        <StatusRow label="Agent" ok={status.agent.installed} text={status.agent.installed ? `v${status.agent.version || '?'}` : 'Not installed'} />
        <StatusRow label="Accessibility" ok={status.accessibility.enabled} text={status.accessibility.enabled ? 'Enabled' : 'Disabled'} />
      </div>

      {/* Platforms */}
      {status.platforms.length > 0 && (
        <div className="border-t border-[--line-1] px-4 py-3">
          <p className="mb-1 text-[10px] font-medium text-[--txt-3]">Platforms</p>
          <div className="space-y-1">
            {status.platforms.map((p) => (
              <div key={p.name || p.package} className="flex items-center justify-between text-[10px]">
                <span className="text-[--txt-2]">{PLATFORM_ICONS[p.name?.toLowerCase() || ''] || ''} {p.name}</span>
                {p.installed ? (
                  <span className="text-emerald-400">v{p.version || '?'}</span>
                ) : (
                  <span className="text-red-400">Not installed</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="border-t border-[--line-1] px-4 py-2 text-[10px] text-[--txt-3]">
        {status.last_activity && (
          <div>Last activity: {new Date(status.last_activity).toLocaleString()}</div>
        )}
        <div>Warmup sessions: {status.warmup_count}</div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-1 border-t border-[--line-1] px-4 py-3">
        {onWarmup && (
          <Button variant="ghost" size="sm" onClick={onWarmup} leftIcon={<Flame className="h-3 w-3" />}>Warmup</Button>
        )}
        {onScreenshot && (
          <Button variant="ghost" size="sm" onClick={onScreenshot} leftIcon={<Camera className="h-3 w-3" />}>Screenshot</Button>
        )}
        {onSchedule && (
          <Button variant="ghost" size="sm" onClick={onSchedule} leftIcon={<CalendarClock className="h-3 w-3" />}>Schedule</Button>
        )}
        {onScanDms && (
          <Button variant="ghost" size="sm" onClick={onScanDms} leftIcon={<MessageSquare className="h-3 w-3" />}>Scan DMs</Button>
        )}
        {hasIssues && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onFixEverything}
            leftIcon={<Wrench className="h-3 w-3" />}
            className="animate-pulse border-amber-500/50 text-amber-400 hover:bg-amber-500/10"
          >
            Fix Everything
          </Button>
        )}
      </div>
    </div>
  )
}

function StatusRow({ label, ok, text }: { label: string; ok: boolean; text: string }) {
  return (
    <div className="flex items-center justify-between text-[10px]">
      <span className="text-[--txt-3]">{label}</span>
      <span className={ok ? 'text-emerald-400' : 'text-red-400'}>
        {ok ? '✅' : '❌'} {text}
      </span>
    </div>
  )
}
