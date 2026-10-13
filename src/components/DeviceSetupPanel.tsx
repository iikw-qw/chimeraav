import { useState } from 'react'
import {
  CheckCircle,
  Circle,
  Flame,
  CalendarClock,
  Loader2,
  Plug,
  Search,
  Shield,
  Smartphone,
  XCircle,
} from 'lucide-react'
import { Button } from './ui'
import { api } from '../api/client'
import { toast } from '../hooks/useToast'
import { cn } from '../lib/cn'

type StepStatus = 'idle' | 'checking' | 'ok' | 'error'

interface Props {
  serial: string | null
  onComplete?: () => void
  onSelectDevice?: (serial: string) => void
  compact?: boolean
}

export function DeviceSetupPanel({ serial, onComplete, onSelectDevice, compact }: Props) {
  const [connectionStatus, setConnectionStatus] = useState<StepStatus>('idle')
  const [agentStatus, setAgentStatus] = useState<'idle' | 'checking' | 'not_installed' | 'installing' | 'installed' | 'error'>('idle')
  const [platformsStatus, setPlatformsStatus] = useState<StepStatus>('idle')
  const [platforms, setPlatforms] = useState<string[]>([])
  const [deviceName, setDeviceName] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [showManual, setShowManual] = useState(false)

  const allGood = connectionStatus === 'ok' && (agentStatus === 'installed' || agentStatus === 'idle') && platformsStatus === 'ok'

  const checkConnection = async () => {
    setConnectionStatus('checking')
    setErrorMessage('')
    try {
      let res = await api.get('/api/devices')
      let devices = res.data as any[]
      if (devices.length === 0) {
        const fallback = await api.get('/api/devices/adb')
        if (Array.isArray(fallback.data) && fallback.data.length > 0) {
          devices = fallback.data
        }
      }
      if (devices.length > 0) {
        setConnectionStatus('ok')
        const dev = devices[0]
        setDeviceName(dev.name || dev.serial || dev.id)
        if (!serial && onSelectDevice) {
          onSelectDevice(dev.serial || dev.id)
        }
      } else {
        setConnectionStatus('error')
        setRetryCount((c) => c + 1)
        setErrorMessage(
          'No devices found. Please:\n1. Connect phone via USB\n2. Enable Developer Options (tap Build Number 7 times)\n3. Enable USB Debugging\n4. Tap "Allow" on the phone prompt',
        )
      }
    } catch {
      setConnectionStatus('error')
      setErrorMessage('Cannot reach sidecar. Is it running?')
    }
  }

  const installAgent = async () => {
    if (!serial) {
      setErrorMessage('Select a device first')
      return
    }
    setAgentStatus('installing')
    setErrorMessage('')
    try {
      const res = await api.post(`/api/v1/agent/install/${serial}`)
      const data = res.data
      if (data.status === 'ok' || data.ok) {
        setAgentStatus('installed')
        toast.success('Agent installed')
      } else {
        setAgentStatus('error')
        setErrorMessage(data.message || 'Install failed')
      }
    } catch (e: any) {
      setAgentStatus('error')
      setErrorMessage(e.message || 'Install request failed')
    }
  }

  const detectApps = async () => {
    if (!serial) {
      setErrorMessage('Select a device first')
      return
    }
    setPlatformsStatus('checking')
    setErrorMessage('')
    try {
      const res = await api.get(`/api/v1/devices/${serial}/platforms?force=true`)
      const data = res.data as any[]
      const installed = data.filter((p: any) => p.installed)
      if (installed.length > 0) {
        setPlatformsStatus('ok')
        setPlatforms(installed.map((p: any) => p.name || p.platform))
      } else {
        setPlatformsStatus('error')
        setErrorMessage(
          'No social apps found on device.\nOpen Google Play Store and install:\n• Instagram\n• TikTok\n• Threads\nThen click "Detect Apps" again.',
        )
      }
    } catch {
      setPlatformsStatus('error')
    }
  }

  const verifyEverything = async () => {
    setErrorMessage('')
    await checkConnection()
    if (!serial) return

    try {
      const agentRes = await api.get(`/api/v1/agent/status/${serial}`)
      const agentData = agentRes.data as any
      setAgentStatus(agentData.installed ? 'installed' : 'not_installed')
    } catch {
      setAgentStatus('error')
    }

    await detectApps()

    if (agentStatus === 'installed' && serial) {
      try {
        const testRes = await api.post(`/api/v1/devices/${serial}/self-test`)
        const testData = testRes.data as any
        if (!testData.all_passed) {
          setErrorMessage(`Self-test: ${testData.summary}`)
        }
      } catch {}
    }
  }

  const stepIcon = (status: string) => {
    if (status === 'ok' || status === 'installed') return <CheckCircle className="h-4 w-4 text-emerald-400" />
    if (status === 'error' || status === 'not_installed') return <XCircle className="h-4 w-4 text-red-400" />
    if (status === 'checking' || status === 'installing') return <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
    return <Circle className="h-4 w-4 text-[--txt-3]" />
  }

  const stepLabel = (step: number) => {
    if (step === 1) {
      if (connectionStatus === 'ok') return `Connected: ${deviceName}`
      if (connectionStatus === 'error') return 'Not found — enable USB Debugging'
      return 'Not checked'
    }
    if (step === 2) {
      if (agentStatus === 'installed') return 'Agent installed and running'
      if (agentStatus === 'not_installed') return 'Agent not installed'
      if (agentStatus === 'installing') return 'Installing...'
      if (agentStatus === 'error') return 'Agent install failed'
      return 'Not checked'
    }
    if (step === 3) {
      if (platformsStatus === 'ok') return `Found: ${platforms.join(', ')}`
      if (platformsStatus === 'error') return 'No social apps — install from Play Store'
      return 'Not checked'
    }
    return ''
  }

  return (
    <div className={cn('rounded-xl border border-[--line-1] bg-[--bg-1]', compact ? 'p-3' : 'p-5')}>
      <div className="mb-3 flex items-center gap-2">
        <Smartphone className="h-5 w-5 text-[--blue]" />
        <h3 className="text-sm font-semibold text-[--txt-1]">Device Setup</h3>
        <span className="ml-auto text-[10px] text-[--txt-3]">{deviceName || 'No device selected'}</span>
      </div>

      <div className="space-y-3">
        {/* Step 1 */}
        <div className="flex items-center gap-3">
          {stepIcon(connectionStatus)}
          <div className="flex-1">
            <div className="text-xs font-medium text-[--txt-1]">Step 1: Connection</div>
            <div className="text-[10px] text-[--txt-3]">{stepLabel(1)}</div>
          </div>
          <Button variant="secondary" size="sm" onClick={checkConnection} disabled={connectionStatus === 'checking'}>
            <Plug className="mr-1 h-3 w-3" /> Check
          </Button>
        </div>

        {/* Step 2 */}
        <div className="flex items-center gap-3">
          {stepIcon(agentStatus)}
          <div className="flex-1">
            <div className="text-xs font-medium text-[--txt-1]">Step 2: Chimera Agent</div>
            <div className="text-[10px] text-[--txt-3]">{stepLabel(2)}</div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={installAgent}
            disabled={!serial || agentStatus === 'installing'}
          >
            <Shield className="mr-1 h-3 w-3" /> Install
          </Button>
        </div>

        {/* Step 3 */}
        <div className="flex items-center gap-3">
          {stepIcon(platformsStatus)}
          <div className="flex-1">
            <div className="text-xs font-medium text-[--txt-1]">Step 3: Social Apps</div>
            <div className="text-[10px] text-[--txt-3]">{stepLabel(3)}</div>
          </div>
          <Button variant="secondary" size="sm" onClick={detectApps} disabled={!serial || platformsStatus === 'checking'}>
            <Search className="mr-1 h-3 w-3" /> Detect
          </Button>
        </div>

        {/* Step 4 */}
        <div className="flex items-center gap-3">
          <Circle className="h-4 w-4 text-[--txt-3]" />
          <div className="flex-1">
            <div className="text-xs font-medium text-[--txt-1]">Step 4: Final Check</div>
          </div>
          <Button variant="secondary" size="sm" onClick={verifyEverything}>
            Verify All
          </Button>
        </div>
      </div>

      {/* Error */}
      {errorMessage && (
        <div className="mt-3 whitespace-pre-line rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-[10px] text-red-400">
          {errorMessage}
        </div>
      )}

      {/* Manual setup link after 3 failures */}
      {retryCount >= 3 && !showManual && (
        <button
          type="button"
          onClick={() => setShowManual(true)}
          className="mt-2 text-[10px] text-amber-400 underline"
        >
          Auto-detect not working? Open Manual Setup Guide
        </button>
      )}

      {/* Success */}
      {allGood && (
        <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-400">
            <CheckCircle className="h-4 w-4" /> Device ready for warmup and scheduling
          </div>
          <div className="mt-2 flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { onComplete?.(); window.location.hash = '#/warmup' }}
              leftIcon={<Flame className="h-3.5 w-3.5" />}
            >
              Start Warmup
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { onComplete?.(); window.location.hash = '#/scheduler' }}
              leftIcon={<CalendarClock className="h-3.5 w-3.5" />}
            >
              Open Scheduler
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
