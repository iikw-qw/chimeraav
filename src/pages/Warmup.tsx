import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart3,
  CheckCircle,
  ChevronDown,
  Download,
  Eye,
  Flame,
  Heart,
  MessageCircle,
  Moon,
  Pause,
  Play,
  Plus,
  RefreshCw,
  ScrollText,
  Search,
  Settings,
  Sparkles,
  Square,
  Trash2,
  Save,
  User,
  Wifi,
  X,
} from 'lucide-react'
import { Badge, Button, Card, CardBody, CardHeader } from '../components/ui'
import { NoPlatformsError } from '../components/NoPlatformsError'
import { DevicePlatformError } from '../components/DevicePlatformError'
import { DeviceSetupPanel } from '../components/DeviceSetupPanel'
import { FixEverythingWizard } from '../components/FixEverythingWizard'
import { DebugOverlay } from '../components/DebugOverlay'
import { useWebSocket } from '../utils/useWebSocket'
import { useDevices, type Device } from '../hooks/useDevices'
import { api } from '../api/client'
import { toast } from '../hooks/useToast'
import DeviceSetupGuide from '../components/DeviceSetupGuide'
import { cn } from '../lib/cn'

interface PlatformInfo {
  platform: string
  name?: string
  package: string
  installed: boolean
  version: string
  supports_posting?: boolean
  supports_stories?: boolean
  supports_reels?: boolean
}

interface WarmupStats {
  total_scrolls: number
  total_likes: number
  total_profiles: number
  total_stories: number
  total_dms: number
  elapsed_seconds: number
  current_action_label: string
  action: string
  platform: string
  action_count: number
  log_entry?: { time: string; action: string; detail: string }
}

interface Preset {
  id?: number
  name: string
  weights: Record<string, number>
  platforms: string[]
  mode: string
  intensity: number
  night_mode: boolean
}

interface LogEntry {
  time: string
  action: string
  detail: string
}

const DEFAULT_WEIGHTS: Record<string, number> = {
  scroll_feed: 28, like_post: 18, visit_profile: 12, deep_profile: 8,
  view_story: 10, search: 5, chaotic_swipe: 7, dm_scan: 4, pause: 8,
}

const WEIGHT_LABELS: Record<string, string> = {
  scroll_feed: 'Scroll Feed', like_post: 'Like Post', visit_profile: 'Visit Profile',
  deep_profile: 'Deep Profile', view_story: 'View Stories', search: 'Search',
  chaotic_swipe: 'Chaotic Swipes', dm_scan: 'DM Scan', pause: 'Pause',
}

const INTENSITY_LABELS = ['', 'Light', 'Light', 'Light', 'Medium', 'Medium', 'Medium', 'Aggressive', 'Aggressive', 'Aggressive', 'Aggressive']
const MODE_OPTIONS = [
  { value: 'single', label: 'Single platform' },
  { value: 'sequential', label: 'Sequential' },
  { value: 'random_switch', label: 'Random switch' },
]

const PLATFORM_ICONS: Record<string, string> = {
  instagram: '📸', tiktok: '🎵', threads: '💬',
  twitter: '🐦', facebook: '📱', youtube: '▶️', linkedin: '💼',
}

export function WarmupPage() {
  const { data: devices = [], refetch: refetchDevices } = useDevices()
  const deviceList = useMemo(() => (Array.isArray(devices) ? devices : []) as Device[], [devices])

  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set())
  const [devicePlatforms, setDevicePlatforms] = useState<Record<string, PlatformInfo[]>>({})
  const [selectedPlatforms, setSelectedPlatforms] = useState<Record<string, Set<string>>>({})
  const [samePlatformsAll, setSamePlatformsAll] = useState(true)
  const [mode, setMode] = useState('single')
  const [intensity, setIntensity] = useState(5)
  const [nightMode, setNightMode] = useState(false)
  const [weights, setWeights] = useState<Record<string, number>>({ ...DEFAULT_WEIGHTS })
  const [perPlatformWeights, setPerPlatformWeights] = useState(false)
  const [platformWeights, setPlatformWeights] = useState<Record<string, Record<string, number>>>({})
  const [activePlatformTab, setActivePlatformTab] = useState('')
  const [running, setRunning] = useState(false)
  const [paused, setPaused] = useState(false)
  const [stats, setStats] = useState<WarmupStats | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showLists, setShowLists] = useState(false)
  const [actionLog, setActionLog] = useState<LogEntry[]>([])
  const [apiError, setApiError] = useState<any>(null)
  const [showNoPlatforms, setShowNoPlatforms] = useState(false)
  const [showFixWizard, setShowFixWizard] = useState(false)
  const [debugMode, setDebugMode] = useState(false)
  const [debugEvents, setDebugEvents] = useState<any[]>([])
  const [showReport, setShowReport] = useState(false)
  const [reportData, setReportData] = useState<any>(null)
  const [deviceAccounts, setDeviceAccounts] = useState<any[]>([])
  const [selectedAccount, setSelectedAccount] = useState<any>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const [blacklist, setBlacklist] = useState<any[]>([])
  const [whitelist, setWhitelist] = useState<any[]>([])
  const [blInput, setBlInput] = useState('')
  const [blPlatform, setBlPlatform] = useState('instagram')
  const [wlInput, setWlInput] = useState('')
  const [wlPlatform, setWlPlatform] = useState('instagram')
  const [wlBoost, setWlBoost] = useState(2)

  const [presets, setPresets] = useState<Preset[]>([])
  const [presetName, setPresetName] = useState('')
  const [showPresetDropdown, setShowPresetDropdown] = useState(false)

  const firstSelectedDevice = useMemo(() => [...selectedDevices][0] || '', [selectedDevices])

  const allSelectedPlatforms = useMemo(() => {
    const all = new Set<string>()
    Object.values(selectedPlatforms).forEach((s) => s.forEach((p) => all.add(p)))
    return all
  }, [selectedPlatforms])

  const toggleDevice = (id: string) => {
    setSelectedDevices((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  useEffect(() => {
    selectedDevices.forEach((serial) => {
      if (!devicePlatforms[serial]) {
        api.get(`/api/v1/devices/${serial}/platforms`)
          .then((r) => {
            const data = r.data as PlatformInfo[]
            setDevicePlatforms((prev) => ({ ...prev, [serial]: data }))
            const installed = data.filter((p) => p.installed)
            if (installed.length === 0) setShowNoPlatforms(true)
            if (!selectedPlatforms[serial]) {
              setSelectedPlatforms((prev) => ({
                ...prev,
                [serial]: new Set(installed.length > 0 ? [installed[0].platform] : []),
              }))
            }
          })
          .catch(() => {})
      }
    })
  }, [selectedDevices])

  useEffect(() => {
    if (showNoPlatforms && firstSelectedDevice) {
      const interval = setInterval(() => {
        api.get(`/api/v1/devices/${firstSelectedDevice}/platforms?force=true`)
          .then((r) => {
            const data = r.data as PlatformInfo[]
            setDevicePlatforms((prev) => ({ ...prev, [firstSelectedDevice]: data }))
            const installed = data.filter((p) => p.installed)
            if (installed.length > 0) {
              setShowNoPlatforms(false)
              setSelectedPlatforms((prev) => ({
                ...prev,
                [firstSelectedDevice]: new Set([installed[0].platform]),
              }))
            }
          })
          .catch(() => {})
      }, 10000)
      return () => clearInterval(interval)
    }
  }, [showNoPlatforms, firstSelectedDevice])

  useEffect(() => {
    if (firstSelectedDevice) {
      api.get(`/api/v1/devices/${firstSelectedDevice}/accounts`)
        .then((r) => {
          const accs = r.data as any[]
          setDeviceAccounts(accs)
          setSelectedAccount(accs.find((a: any) => a.is_primary) || accs[0] || null)
        })
        .catch(() => setDeviceAccounts([]))
    } else {
      setDeviceAccounts([])
      setSelectedAccount(null)
    }
  }, [firstSelectedDevice])

  useEffect(() => {
    api.get('/api/v1/warmup/blacklist').then((r) => setBlacklist(r.data as any[])).catch(() => {})
    api.get('/api/v1/warmup/whitelist').then((r) => setWhitelist(r.data as any[])).catch(() => {})
    api.get('/api/v1/warmup/presets').then((r) => setPresets(r.data as Preset[])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!running || !firstSelectedDevice) return
    const ws = new WebSocket(`ws://localhost:17842/api/ws/warmup/${firstSelectedDevice}`)
    wsRef.current = ws
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as WarmupStats & { event?: string; debug?: any }
        if (data.event === 'finished') {
          setRunning(false)
          return
        }
        setStats(data)
        setElapsed(data.elapsed_seconds)
        if (data.log_entry) {
          setActionLog((prev) => [...prev.slice(-19), data.log_entry!])
        }
        if (data.debug) {
          setDebugEvents((prev) => [...prev.slice(-49), data.debug])
        }
      } catch {}
    }
    return () => ws.close()
  }, [running, firstSelectedDevice])

  const togglePlatform = (serial: string, platform: string) => {
    if (samePlatformsAll) {
      setSelectedPlatforms((prev) => {
        const next: Record<string, Set<string>> = {}
        selectedDevices.forEach((s) => {
          const cur = new Set(prev[s] || [])
          if (cur.has(platform)) cur.delete(platform)
          else cur.add(platform)
          next[s] = cur
        })
        return { ...prev, ...next }
      })
    } else {
      setSelectedPlatforms((prev) => {
        const cur = new Set(prev[serial] || [])
        if (cur.has(platform)) cur.delete(platform)
        else cur.add(platform)
        return { ...prev, [serial]: cur }
      })
    }
  }

  const canStart = selectedDevices.size > 0 && allSelectedPlatforms.size > 0

  const startWarmup = async () => {
    if (!canStart) {
      toast.warning('Select a device and platform')
      return
    }
    setRunning(true)
    setStats(null)
    setElapsed(0)
    setActionLog([])
    setDebugEvents([])
    setPaused(false)
    setApiError(null)

    const serial = firstSelectedDevice
    const plats = [...(selectedPlatforms[serial] || [])]

    try {
      await api.post('/api/v1/warmup/full', {
        serial,
        platforms: plats,
        platform: plats[0],
        intensity,
        mode,
        night_mode: nightMode,
        custom_weights: perPlatformWeights ? undefined : weights,
        custom_weights_per_platform: perPlatformWeights ? platformWeights : undefined,
        debug: debugMode,
        account: selectedAccount?.username,
        account_user_id: selectedAccount?.user_id ?? 0,
      })
      toast.success('Warmup completed')
      setRunning(false)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      if (detail && typeof detail === 'object' && detail.error) {
        setApiError(detail)
      } else {
        toast.danger(err.message || 'Failed')
      }
      setRunning(false)
    }
  }

  const stopWarmup = async () => {
    if (!firstSelectedDevice) return
    try {
      await api.post(`/api/v1/warmup/stop/${firstSelectedDevice}`)
      setRunning(false)
      setPaused(false)
      toast.success('Warmup stopped')
    } catch (err: any) {
      toast.danger(err.message)
    }
  }

  const togglePause = async () => {
    if (!firstSelectedDevice) return
    try {
      if (paused) {
        await api.post(`/api/v1/warmup/unpause/${firstSelectedDevice}`)
        setPaused(false)
      } else {
        await api.post(`/api/v1/warmup/pause/${firstSelectedDevice}`)
        setPaused(true)
      }
    } catch (err: any) {
      toast.danger(err.message)
    }
  }

  const addBlacklist = async () => {
    if (!blInput) return
    await api.post('/api/v1/warmup/blacklist', { username: blInput, platform: blPlatform })
    setBlInput('')
    api.get('/api/v1/warmup/blacklist').then((r) => setBlacklist(r.data as any[]))
  }

  const removeBlacklist = async (username: string, platform: string) => {
    await api.delete('/api/v1/warmup/blacklist', { data: { username, platform } })
    api.get('/api/v1/warmup/blacklist').then((r) => setBlacklist(r.data as any[]))
  }

  const addWhitelist = async () => {
    if (!wlInput) return
    await api.post('/api/v1/warmup/whitelist', { username: wlInput, platform: wlPlatform, boost_factor: wlBoost })
    setWlInput('')
    api.get('/api/v1/warmup/whitelist').then((r) => setWhitelist(r.data as any[]))
  }

  const removeWhitelist = async (username: string, platform: string) => {
    await api.delete('/api/v1/warmup/whitelist', { data: { username, platform } })
    api.get('/api/v1/warmup/whitelist').then((r) => setWhitelist(r.data as any[]))
  }

  const saveCurrentPreset = async () => {
    if (!presetName) return
    await api.post('/api/v1/warmup/presets', {
      name: presetName, weights, platforms: [...allSelectedPlatforms],
      mode, intensity, night_mode: nightMode,
    })
    setPresetName('')
    api.get('/api/v1/warmup/presets').then((r) => setPresets(r.data as Preset[]))
    toast.success('Preset saved')
  }

  const loadPreset = (preset: Preset) => {
    setWeights(preset.weights || { ...DEFAULT_WEIGHTS })
    setMode(preset.mode || 'single')
    setIntensity(preset.intensity ?? 5)
    setNightMode(preset.night_mode ?? false)
    setShowPresetDropdown(false)
    toast.success(`Loaded preset: ${preset.name}`)
  }

  const fetchReport = async () => {
    if (!firstSelectedDevice) return
    try {
      const r = await api.get(`/api/v1/warmup/report/${firstSelectedDevice}`)
      setReportData(r.data)
      setShowReport(true)
    } catch {
      toast.danger('No report available')
    }
  }

  const exportReportJSON = () => {
    if (!reportData) return
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `warmup-report-${reportData.serial || 'unknown'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportReportCSV = () => {
    if (!reportData?.stats) return
    const s = reportData.stats
    const csv = `Metric,Value\nScrolls,${s.scrolls}\nLikes,${s.likes}\nProfiles,${s.profiles}\nStories,${s.stories}\nDMs,${s.dms}\nTotal Actions,${s.total_actions}\nActions/min,${s.actions_per_minute}\nDuration,${reportData.duration_display}\n`
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `warmup-report-${reportData.serial || 'unknown'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const refetchPlatforms = () => {
    if (firstSelectedDevice) {
      api.get(`/api/v1/devices/${firstSelectedDevice}/platforms?force=true`)
        .then((r) => {
          const data = r.data as PlatformInfo[]
          setDevicePlatforms((prev) => ({ ...prev, [firstSelectedDevice]: data }))
          const installed = data.filter((p) => p.installed)
          if (installed.length > 0) setShowNoPlatforms(false)
          toast.success(`Found ${installed.length} platforms`)
        })
        .catch(() => toast.danger('Failed to detect platforms'))
    }
  }

  const mm = Math.floor(elapsed / 60).toString().padStart(2, '0')
  const ss = (elapsed % 60).toString().padStart(2, '0')
  const estMinutes = 10 + intensity * 3
  const progressPercent = estMinutes > 0 ? Math.min(100, Math.round((elapsed / 60 / estMinutes) * 100)) : 0

  return (
    <motion.div
      className="flex h-full overflow-hidden bg-[--bg-0]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {/* Sidebar config */}
      <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto border-r border-[--line-1] bg-[--bg-1] p-5">
        <div className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-[--amber]" />
          <h2 className="text-lg font-semibold text-[--txt-1]">Warmup</h2>
          <button type="button" onClick={() => setNightMode(!nightMode)} className={cn(
            'ml-auto flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium transition-all',
            nightMode ? 'bg-indigo-500/20 text-indigo-400' : 'bg-[--bg-2] text-[--txt-3]',
          )}>
            <Moon className="h-3 w-3" /> Night
          </button>
        </div>

        {/* Device grid */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <label className="text-xs font-medium text-[--txt-3]">Devices ({selectedDevices.size} selected)</label>
            <button type="button" onClick={() => refetchDevices()} className="text-[10px] text-[--txt-3] hover:text-[--txt-2]">
              <RefreshCw className="inline h-3 w-3" /> Refresh
            </button>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {deviceList.map((d) => {
              const isSelected = selectedDevices.has(d.id)
              const isOnline = d.status === 'online'
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => isOnline && toggleDevice(d.id)}
                  disabled={!isOnline}
                  className={cn(
                    'rounded-lg border p-2 text-left text-[10px] transition-all',
                    !isOnline && 'cursor-not-allowed opacity-40',
                    isSelected
                      ? 'border-[--blue] bg-[--blue-glow]'
                      : 'border-[--line-1] bg-[--bg-2] hover:bg-[--bg-3]',
                  )}
                >
                  <div className="flex items-center gap-1">
                    {isSelected && <CheckCircle className="h-3 w-3 text-[--blue]" />}
                    <span className={cn('truncate font-medium', isSelected ? 'text-[--blue]' : 'text-[--txt-2]')}>
                      {d.name || d.id.slice(0, 10)}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1 text-[9px] text-[--txt-3]">
                    <span className={cn('h-1.5 w-1.5 rounded-full', isOnline ? 'bg-[--green]' : 'bg-[--red]')} />
                    {(d as any).model || d.status}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* No platforms error */}
        {showNoPlatforms && firstSelectedDevice && (
          <>
            <NoPlatformsError
              serial={firstSelectedDevice}
              onRetry={refetchPlatforms}
              onConnect={() => api.post(`/api/v1/agent/install/${firstSelectedDevice}`).catch(() => {})}
            />
            <DeviceSetupPanel
              serial={firstSelectedDevice}
              compact
              onComplete={() => {
                setShowNoPlatforms(false)
                refetchPlatforms()
              }}
            />
          </>
        )}

        {/* Platforms per device */}
        {selectedDevices.size > 0 && !showNoPlatforms && (
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs font-medium text-[--txt-3]">Platforms</label>
              {selectedDevices.size > 1 && (
                <label className="flex items-center gap-1 text-[10px] text-[--txt-3]">
                  <input type="checkbox" checked={samePlatformsAll} onChange={(e) => setSamePlatformsAll(e.target.checked)} className="accent-[--blue]" />
                  Same for all
                </label>
              )}
            </div>
            {[...selectedDevices].map((serial) => {
              const plats = devicePlatforms[serial] || []
              const selected = selectedPlatforms[serial] || new Set()
              return (
                <div key={serial} className="mb-2">
                  {selectedDevices.size > 1 && (
                    <div className="mb-1 text-[9px] text-[--txt-3]">{serial.slice(0, 12)}...</div>
                  )}
                  <div className="flex flex-wrap gap-1">
                    {plats.map((p) => (
                      <button
                        key={p.platform}
                        type="button"
                        onClick={() => p.installed && togglePlatform(serial, p.platform)}
                        disabled={!p.installed}
                        className={cn(
                          'rounded-lg border px-2 py-1 text-[10px] font-medium transition-all',
                          !p.installed && 'cursor-not-allowed opacity-30',
                          selected.has(p.platform)
                            ? 'border-[--blue] bg-[--blue-glow] text-[--blue]'
                            : 'border-[--line-1] bg-[--bg-2] text-[--txt-2] hover:bg-[--bg-3]',
                        )}
                      >
                        {PLATFORM_ICONS[p.platform] || ''} {p.platform}
                        {!p.installed && ' (N/A)'}
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Multi-account selector */}
        {deviceAccounts.length > 0 && firstSelectedDevice && (
          <div>
            <label className="mb-1 block text-xs font-medium text-[--txt-3]">Account</label>
            <div className="space-y-1">
              {deviceAccounts
                .filter((a: any) => !allSelectedPlatforms.size || allSelectedPlatforms.has(a.platform))
                .map((a: any) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => setSelectedAccount(a)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-[10px] transition-all',
                      selectedAccount?.id === a.id
                        ? 'border-[--blue] bg-[--blue-glow]'
                        : 'border-[--line-1] bg-[--bg-2] hover:bg-[--bg-3]',
                    )}
                  >
                    <span className={cn('font-medium', selectedAccount?.id === a.id ? 'text-[--blue]' : 'text-[--txt-2]')}>
                      @{a.username}
                    </span>
                    <span className="text-[9px] text-[--txt-3]">
                      {a.is_primary ? '(Primary)' : `(${a.clone_method || 'Clone'})`}
                    </span>
                    <span className="ml-auto text-[9px] text-[--txt-3]">{a.platform}</span>
                  </button>
                ))}
            </div>
          </div>
        )}

        {/* Mode */}
        {allSelectedPlatforms.size > 1 && (
          <div>
            <label className="mb-1 block text-xs font-medium text-[--txt-3]">Warmup Mode</label>
            <div className="flex flex-col gap-1">
              {MODE_OPTIONS.map((o) => (
                <label key={o.value} className="flex items-center gap-2 text-xs text-[--txt-2]">
                  <input type="radio" name="mode" value={o.value} checked={mode === o.value} onChange={() => setMode(o.value)} className="accent-[--blue]" />
                  {o.label}
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Intensity */}
        <div>
          <label className="mb-1 flex items-center justify-between text-xs font-medium text-[--txt-3]">
            <span>Intensity</span>
            <span className="text-[--txt-1]">{intensity} — {INTENSITY_LABELS[intensity]} (~{estMinutes}m)</span>
          </label>
          <input type="range" min={1} max={10} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} className="w-full accent-[--blue]" />
        </div>

        {/* Advanced settings */}
        <button type="button" onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1 text-xs text-[--txt-3] hover:text-[--txt-2]">
          <ChevronDown className={cn('h-3 w-3 transition-transform', showAdvanced && 'rotate-180')} /> Advanced Settings
        </button>

        {showAdvanced && (
          <div className="space-y-2">
            {/* Presets */}
            <div className="flex gap-1">
              <input value={presetName} onChange={(e) => setPresetName(e.target.value)} placeholder="Preset name" className="flex-1 rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-[10px] text-[--txt-1]" />
              <button type="button" onClick={saveCurrentPreset} className="rounded bg-[--blue] px-2 py-1 text-[10px] text-white"><Save className="h-3 w-3" /></button>
              <div className="relative">
                <button type="button" onClick={() => setShowPresetDropdown(!showPresetDropdown)} className="rounded bg-[--bg-2] px-2 py-1 text-[10px] text-[--txt-2]">Load</button>
                {showPresetDropdown && presets.length > 0 && (
                  <div className="absolute right-0 top-full z-10 mt-1 w-40 rounded-md border border-[--line-1] bg-[--bg-1] py-1 shadow-lg">
                    {presets.map((p) => (
                      <button key={p.name} type="button" onClick={() => loadPreset(p)} className="block w-full px-3 py-1 text-left text-[10px] text-[--txt-2] hover:bg-[--bg-2]">{p.name}</button>
                    ))}
                  </div>
                )}
              </div>
              <button type="button" onClick={() => setWeights({ ...DEFAULT_WEIGHTS })} className="rounded bg-[--bg-2] px-2 py-1 text-[10px] text-[--txt-2]">Reset</button>
            </div>

            {/* Per-platform toggle */}
            {allSelectedPlatforms.size > 1 && (
              <label className="flex items-center gap-2 text-[10px] text-[--txt-3]">
                <input type="checkbox" checked={perPlatformWeights} onChange={(e) => setPerPlatformWeights(e.target.checked)} className="accent-[--blue]" />
                Custom weights per platform
              </label>
            )}

            {/* Platform tabs */}
            {perPlatformWeights && allSelectedPlatforms.size > 1 ? (
              <div>
                <div className="flex gap-1 border-b border-[--line-1] pb-1">
                  {[...allSelectedPlatforms].map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setActivePlatformTab(p)}
                      className={cn(
                        'rounded-t px-2 py-1 text-[10px]',
                        (activePlatformTab || [...allSelectedPlatforms][0]) === p
                          ? 'bg-[--blue-glow] text-[--blue]'
                          : 'text-[--txt-3] hover:text-[--txt-2]',
                      )}
                    >
                      {PLATFORM_ICONS[p] || ''} {p}
                    </button>
                  ))}
                </div>
                {Object.entries(platformWeights[activePlatformTab || [...allSelectedPlatforms][0]] || DEFAULT_WEIGHTS).map(([key, val]) => (
                  <div key={key} className="mt-1">
                    <div className="flex justify-between text-[10px] text-[--txt-3]">
                      <span>{WEIGHT_LABELS[key] ?? key}</span><span>{val}</span>
                    </div>
                    <input
                      type="range" min={0} max={100} value={val}
                      onChange={(e) => {
                        const tab = activePlatformTab || [...allSelectedPlatforms][0]
                        setPlatformWeights((prev) => ({
                          ...prev,
                          [tab]: { ...(prev[tab] || DEFAULT_WEIGHTS), [key]: Number(e.target.value) },
                        }))
                      }}
                      className="w-full accent-[--blue]"
                    />
                  </div>
                ))}
              </div>
            ) : (
              Object.entries(weights).map(([key, val]) => (
                <div key={key}>
                  <div className="flex justify-between text-[10px] text-[--txt-3]">
                    <span>{WEIGHT_LABELS[key] ?? key}</span><span>{val}</span>
                  </div>
                  <input type="range" min={0} max={100} value={val} onChange={(e) => setWeights((prev) => ({ ...prev, [key]: Number(e.target.value) }))} className="w-full accent-[--blue]" />
                </div>
              ))
            )}
          </div>
        )}

        {/* Blacklist / Whitelist */}
        <button type="button" onClick={() => setShowLists(!showLists)} className="flex items-center gap-1 text-xs text-[--txt-3] hover:text-[--txt-2]">
          <ChevronDown className={cn('h-3 w-3 transition-transform', showLists && 'rotate-180')} /> Blacklist / Whitelist
        </button>

        {showLists && (
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[10px] font-medium text-[--txt-3]">Blacklist</label>
              <div className="flex gap-1">
                <input value={blInput} onChange={(e) => setBlInput(e.target.value)} placeholder="@username" className="flex-1 rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-[10px] text-[--txt-1]" />
                <select value={blPlatform} onChange={(e) => setBlPlatform(e.target.value)} className="rounded border border-[--line-2] bg-[--bg-2] px-1 py-1 text-[10px] text-[--txt-1]">
                  <option>instagram</option><option>tiktok</option><option>facebook</option><option>twitter</option><option>threads</option>
                </select>
                <button type="button" onClick={addBlacklist} className="rounded bg-red-500/20 px-2 py-1 text-[10px] text-red-400"><Plus className="h-3 w-3" /></button>
              </div>
              {blacklist.map((b: any, i: number) => (
                <div key={i} className="mt-1 flex items-center justify-between rounded bg-[--bg-2] px-2 py-1 text-[10px]">
                  <span className="text-[--txt-2]">{b.username} ({b.platform})</span>
                  <button type="button" onClick={() => removeBlacklist(b.username, b.platform)}><Trash2 className="h-3 w-3 text-red-400" /></button>
                </div>
              ))}
            </div>
            <div>
              <label className="mb-1 block text-[10px] font-medium text-[--txt-3]">Whitelist</label>
              <div className="flex gap-1">
                <input value={wlInput} onChange={(e) => setWlInput(e.target.value)} placeholder="@username" className="flex-1 rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-[10px] text-[--txt-1]" />
                <select value={wlPlatform} onChange={(e) => setWlPlatform(e.target.value)} className="rounded border border-[--line-2] bg-[--bg-2] px-1 py-1 text-[10px] text-[--txt-1]">
                  <option>instagram</option><option>tiktok</option><option>facebook</option><option>twitter</option><option>threads</option>
                </select>
                <button type="button" onClick={addWhitelist} className="rounded bg-green-500/20 px-2 py-1 text-[10px] text-green-400"><Plus className="h-3 w-3" /></button>
              </div>
              {whitelist.map((w: any, i: number) => (
                <div key={i} className="mt-1 flex items-center justify-between rounded bg-[--bg-2] px-2 py-1 text-[10px]">
                  <span className="text-[--txt-2]">{w.username} ({w.platform}) x{w.boost_factor}</span>
                  <button type="button" onClick={() => removeWhitelist(w.username, w.platform)}><Trash2 className="h-3 w-3 text-red-400" /></button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Validation messages */}
        {selectedDevices.size === 0 && <p className="text-xs text-amber-400">Select a device from the grid above</p>}
        {selectedDevices.size > 0 && allSelectedPlatforms.size === 0 && !showNoPlatforms && <p className="text-xs text-amber-400">Select at least one platform for warmup</p>}

        {/* Debug toggle */}
        <label className="flex items-center gap-2 text-[10px] text-[--txt-3]">
          <input type="checkbox" checked={debugMode} onChange={(e) => setDebugMode(e.target.checked)} className="accent-[--blue]" />
          <Eye className="h-3 w-3" /> Debug View
        </label>

        {/* Start / Stop / Pause */}
        <div className="flex gap-2">
          {!running ? (
            <Button variant="primary" className="flex-1" onClick={startWarmup} disabled={!canStart} leftIcon={<Flame className="h-4 w-4" />}>Start</Button>
          ) : (
            <>
              <Button variant="secondary" size="sm" onClick={togglePause} leftIcon={paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}>
                {paused ? 'Resume' : 'Pause'}
              </Button>
              <Button variant="secondary" className="flex-1" onClick={stopWarmup} leftIcon={<Square className="h-4 w-4" />}>Stop</Button>
            </>
          )}
        </div>
      </aside>

      {/* Main content */}
      <section className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        {apiError && (
          <DevicePlatformError
            error={apiError}
            onRefresh={() => refetchDevices()}
            onDismiss={() => setApiError(null)}
          />
        )}

        {running && (
          <>
            {/* Status bar */}
            <div className="flex flex-wrap items-center gap-3 rounded-lg bg-[--bg-1] px-4 py-2 text-xs">
              <span className="flex items-center gap-1 text-emerald-400">
                <CheckCircle className="h-3.5 w-3.5" /> Device: {firstSelectedDevice.slice(0, 12)}
              </span>
              <span className="flex items-center gap-1 text-emerald-400">
                <CheckCircle className="h-3.5 w-3.5" /> Platform: {stats?.platform || [...allSelectedPlatforms][0]}
              </span>
              {paused && <Badge variant="warning">Paused</Badge>}
            </div>

            {/* Progress bar */}
            <div>
              <div className="mb-1 flex justify-between text-[10px] text-[--txt-3]">
                <span>{progressPercent}%</span>
                <span>{mm}:{ss} / ~{estMinutes}m</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/5">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${progressPercent}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
              <StatBox icon={ScrollText} label="Scrolls" value={stats?.total_scrolls ?? 0} color="text-[--blue]" />
              <StatBox icon={Heart} label="Likes" value={stats?.total_likes ?? 0} color="text-[--red]" />
              <StatBox icon={User} label="Profiles" value={stats?.total_profiles ?? 0} color="text-[--violet]" />
              <StatBox icon={Sparkles} label="Stories" value={stats?.total_stories ?? 0} color="text-[--amber]" />
              <StatBox icon={MessageCircle} label="DMs" value={stats?.total_dms ?? 0} color="text-[--green]" />
              <StatBox icon={Flame} label="Total" value={stats?.action_count ?? 0} color="text-orange-400" />
            </div>

            {/* Current action */}
            <div className="rounded-lg bg-[--bg-1] px-4 py-3">
              <div className="text-sm text-[--txt-1]">
                {stats?.current_action_label ?? 'Starting...'}
              </div>
            </div>

            {/* Action log */}
            {actionLog.length > 0 && (
              <Card>
                <CardHeader>
                  <h3 className="text-xs font-semibold text-[--txt-2]">Action Log</h3>
                </CardHeader>
                <CardBody>
                  <div className="max-h-60 space-y-0.5 overflow-y-auto font-mono text-[10px]">
                    {actionLog.map((entry, i) => (
                      <div key={i} className="text-[--txt-3]">
                        <span className="text-[--txt-2]">[{new Date(entry.time).toLocaleTimeString()}]</span>{' '}
                        {entry.detail}
                      </div>
                    ))}
                  </div>
                </CardBody>
              </Card>
            )}
          </>
        )}

        {/* Report button */}
        {firstSelectedDevice && (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={fetchReport}
              className="flex items-center gap-1.5 rounded-lg border border-[--line-1] bg-[--bg-1] px-3 py-1.5 text-xs text-[--txt-2] hover:bg-[--bg-2]"
            >
              <BarChart3 className="h-3.5 w-3.5" /> Full Report
            </button>
          </div>
        )}

        {!running && selectedDevices.size === 0 && deviceList.length === 0 && (
          <div className="flex flex-1 items-center justify-center py-6">
            <DeviceSetupGuide
              deviceConnected={false}
              agentInstalled={false}
              platformsDetected={[]}
              onCheckConnection={async () => {
                await refetchDevices()
                toast.info('Devices refreshed')
              }}
              onInstallAgent={async () => {
                try {
                  await api.post('/api/v1/devices/install-agent')
                  toast.success('Agent install started')
                } catch {
                  toast.danger('Failed to install agent')
                }
              }}
              onDetectPlatforms={() => toast.info('Connect a device first')}
              onDismiss={() => {}}
            />
          </div>
        )}

        {!running && selectedDevices.size === 0 && deviceList.length > 0 && (
          <div className="flex flex-1 items-center justify-center text-sm text-[--txt-3]">
            Select a device to start warmup
          </div>
        )}

        {!running && selectedDevices.size > 0 && (
          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold text-[--txt-1]">Ready</h3>
            </CardHeader>
            <CardBody>
              <div className="text-xs text-[--txt-2]">
                {selectedDevices.size} device(s) selected, {allSelectedPlatforms.size} platform(s).
                Estimated session: ~{estMinutes} minutes.
              </div>
            </CardBody>
          </Card>
        )}
      </section>

      {/* Report modal */}
      {showReport && reportData && !reportData.error && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="relative w-full max-w-lg rounded-xl border border-[--line-1] bg-[--bg-1] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[--line-1] px-6 py-4">
              <div>
                <h2 className="text-sm font-semibold text-[--txt-1]">
                  Warmup Report — {reportData.platform} — {reportData.started_at ? new Date(reportData.started_at).toLocaleDateString() : ''}
                </h2>
                <p className="text-xs text-[--txt-3]">Duration: {reportData.duration_display}</p>
              </div>
              <button type="button" onClick={() => setShowReport(false)} className="rounded-md p-1 text-[--txt-3] hover:bg-[--bg-2]">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[60vh] space-y-4 overflow-y-auto px-6 py-4">
              {reportData.stats && (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    {(['scrolls', 'likes', 'profiles', 'stories', 'dms', 'total_actions'] as const).map((key) => (
                      <div key={key} className="rounded-lg bg-[--bg-2] p-2 text-center">
                        <div className="font-mono text-lg text-[--txt-1]">{reportData.stats[key]}</div>
                        <div className="text-[10px] text-[--txt-3]">{key.replace('_', ' ')}</div>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-lg bg-[--bg-2] px-3 py-2 text-center text-xs text-[--txt-2]">
                    Actions/minute: <span className="font-mono font-semibold text-[--txt-1]">{reportData.stats.actions_per_minute}</span>
                  </div>
                </>
              )}
              {reportData.encounters?.accounts?.length > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-semibold text-[--txt-2]">Top Encountered Accounts</h3>
                  <div className="space-y-1">
                    {reportData.encounters.accounts.map((a: any, i: number) => (
                      <div key={i} className="flex items-center justify-between rounded bg-[--bg-2] px-3 py-1 text-[10px]">
                        <span className="text-[--txt-2]">@{a.username}</span>
                        <span className="text-[--txt-3]">seen {a.count} times</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-[--line-1] px-6 py-3">
              <button type="button" onClick={exportReportJSON} className="flex items-center gap-1 rounded-md bg-[--bg-2] px-3 py-1.5 text-[10px] text-[--txt-2] hover:bg-[--bg-3]">
                <Download className="h-3 w-3" /> JSON
              </button>
              <button type="button" onClick={exportReportCSV} className="flex items-center gap-1 rounded-md bg-[--bg-2] px-3 py-1.5 text-[10px] text-[--txt-2] hover:bg-[--bg-3]">
                <Download className="h-3 w-3" /> CSV
              </button>
              <button type="button" onClick={() => setShowReport(false)} className="rounded-md bg-[--blue] px-3 py-1.5 text-[10px] text-white hover:opacity-90">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {showFixWizard && firstSelectedDevice && (
        <FixEverythingWizard
          serial={firstSelectedDevice}
          onComplete={() => {
            setShowNoPlatforms(false)
            refetchPlatforms()
          }}
          onClose={() => setShowFixWizard(false)}
        />
      )}
    </motion.div>
  )
}

function StatBox({ icon: Icon, label, value, color }: {
  icon: typeof ScrollText; label: string; value: number; color: string
}) {
  return (
    <div className="rounded-lg border border-[--line-1] bg-[--bg-2] p-3 text-center">
      <Icon className={cn('mx-auto h-5 w-5', color)} />
      <div className="mt-1 font-mono text-lg text-[--txt-1]">{value}</div>
      <div className="text-[10px] text-[--txt-3]">{label}</div>
    </div>
  )
}

export { WarmupPage as Warmup }
