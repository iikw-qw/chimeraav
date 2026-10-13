import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Edit,
  RefreshCw,
  RotateCcw,
  Smartphone,
  Sparkles,
  Trash2,
  Wrench,
  X,
} from 'lucide-react'
import { Badge, Button, Card, CardBody, CardHeader } from '../components/ui'
import { NoPlatformsError } from '../components/NoPlatformsError'
import { DeviceSetupPanel } from '../components/DeviceSetupPanel'
import { FixEverythingWizard } from '../components/FixEverythingWizard'
import DeviceSetupGuide from '../components/DeviceSetupGuide'
import { cn } from '../lib/cn'
import { useDevices, type Device } from '../hooks/useDevices'
import { api } from '../api/client'
import { toast } from '../hooks/useToast'

const DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const
const HOURS = Array.from({ length: 24 }, (_, i) => i)
const REGIONS = ['us', 'europe', 'india', 'uk'] as const
const TONES = ['playful', 'flirty', 'neutral', 'professional', 'motivational', 'funny', 'aesthetic'] as const

const PLATFORM_ICONS: Record<string, string> = {
  instagram: '📸', tiktok: '🎵', threads: '💬', twitter: '🐦',
  facebook: '📱', youtube: '▶️', linkedin: '💼',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'warning', processing: 'info', published: 'success', failed: 'danger', cancelled: 'neutral',
}

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

interface ScheduleCell {
  day: number
  hour: number
  postId?: string
}

interface ScheduledPostItem {
  id: number
  device_serial: string
  platform: string
  caption: string | null
  media_count: number | null
  scheduled_at: string | null
  status: string
  retry_count: number
  last_error: string | null
  hashtags: string[] | null
  location: string | null
  is_prime_time: boolean
  posted_at: string | null
  created_at: string | null
}

type ViewMode = 'wizard' | 'posts'

export function Scheduler() {
  const { data: devices = [], refetch: refetchDevices } = useDevices()
  const deviceList = useMemo(() => (Array.isArray(devices) ? devices : []) as Device[], [devices])

  const [viewMode, setViewMode] = useState<ViewMode>('wizard')
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1)
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState('')
  const [region, setRegion] = useState<typeof REGIONS[number]>('us')
  const [primeHours, setPrimeHours] = useState<number[]>([])
  const [schedule, setSchedule] = useState<ScheduleCell[]>([])
  const [showNoPlatforms, setShowNoPlatforms] = useState(false)
  const [showFixWizard, setShowFixWizard] = useState(false)

  // Accounts for selected device
  const [schedulerAccounts, setSchedulerAccounts] = useState<any[]>([])
  const [schedulerSelectedAccount, setSchedulerSelectedAccount] = useState<any>(null)

  // Step 3 — Post setup
  const [caption, setCaption] = useState('')
  const [captionTone, setCaptionTone] = useState<string>('neutral')
  const [postsPerDay, setPostsPerDay] = useState(3)
  const [hashtags, setHashtags] = useState<string[]>([])
  const [hashtagInput, setHashtagInput] = useState('')
  const [location, setLocation] = useState('')
  const [mentions, setMentions] = useState<string[]>([])
  const [mentionInput, setMentionInput] = useState('')

  // Step 4 — Calendar
  const [calendarMonth, setCalendarMonth] = useState(() => new Date())
  const [selectedDates, setSelectedDates] = useState<string[]>([])

  // Posts list view
  const [posts, setPosts] = useState<ScheduledPostItem[]>([])
  const [postsTotal, setPostsTotal] = useState(0)
  const [postsFilter, setPostsFilter] = useState({ platform: '', status: '', search: '' })
  const [postsSort, setPostsSort] = useState('date')

  useEffect(() => {
    if (selectedDevice) {
      api.get(`/api/v1/devices/${selectedDevice.id}/accounts`)
        .then((r) => {
          const accs = r.data as any[]
          setSchedulerAccounts(accs)
          setSchedulerSelectedAccount(accs.find((a: any) => a.is_primary) || accs[0] || null)
        })
        .catch(() => setSchedulerAccounts([]))
    } else {
      setSchedulerAccounts([])
      setSchedulerSelectedAccount(null)
    }
  }, [selectedDevice])

  useEffect(() => {
    if (!selectedDevice) return
    api.get(`/api/v1/devices/${selectedDevice.id}/platforms?force=true`)
      .then((r) => {
        const data = r.data as PlatformInfo[]
        const installed = data.filter((p) => p.installed)
        setPlatforms(data)
        if (installed.length === 0) setShowNoPlatforms(true)
        else setShowNoPlatforms(false)
      })
      .catch(() => setPlatforms([]))
  }, [selectedDevice])

  useEffect(() => {
    if (showNoPlatforms && selectedDevice) {
      const interval = setInterval(() => {
        api.get(`/api/v1/devices/${selectedDevice.id}/platforms?force=true`)
          .then((r) => {
            const data = r.data as PlatformInfo[]
            setPlatforms(data)
            const installed = data.filter((p) => p.installed)
            if (installed.length > 0) {
              setShowNoPlatforms(false)
              setSelectedPlatform(installed[0].platform)
            }
          })
          .catch(() => {})
      }, 10000)
      return () => clearInterval(interval)
    }
  }, [showNoPlatforms, selectedDevice])

  useEffect(() => {
    api.get(`/api/v1/posts/prime-times?region=${region}`)
      .then((r) => {
        const data = r.data as { prime_slots?: string[] }
        if (data.prime_slots) {
          setPrimeHours(data.prime_slots.map((s) => parseInt(s.split(':')[0], 10)))
        }
      })
      .catch(() => {})
  }, [region])

  const fetchPosts = () => {
    const params = new URLSearchParams()
    if (postsFilter.platform) params.set('platform', postsFilter.platform)
    if (postsFilter.status) params.set('status', postsFilter.status)
    params.set('limit', '50')
    api.get(`/api/v1/schedule/posts?${params}`)
      .then((r) => {
        const data = r.data as { total: number; posts: ScheduledPostItem[] }
        setPosts(data.posts || [])
        setPostsTotal(data.total || 0)
      })
      .catch(() => {})
  }

  useEffect(() => {
    if (viewMode === 'posts') fetchPosts()
  }, [viewMode, postsFilter])

  const onSelectDevice = (d: Device) => {
    setSelectedDevice(d)
    setStep(2)
  }

  const goToStep = (target: 1 | 2 | 3 | 4 | 5) => {
    if (target >= 2 && !selectedDevice) {
      toast.warning('Select a device to continue')
      return
    }
    if (target >= 3 && !selectedPlatform) {
      toast.warning('Select a platform to continue')
      return
    }
    setStep(target)
  }

  const generateCaption = async () => {
    try {
      const r = await api.post('/api/v1/captions/generate', {
        tone: captionTone, include_hashtags: true, hashtag_count: 5,
      })
      const data = r.data as { full_text: string }
      setCaption(data.full_text)
    } catch { toast.danger('Caption generation failed') }
  }

  const addHashtag = () => {
    if (!hashtagInput) return
    const tag = hashtagInput.startsWith('#') ? hashtagInput : `#${hashtagInput}`
    if (!hashtags.includes(tag)) setHashtags((prev) => [...prev, tag])
    setHashtagInput('')
  }

  const addMention = () => {
    if (!mentionInput) return
    const m = mentionInput.startsWith('@') ? mentionInput : `@${mentionInput}`
    if (!mentions.includes(m)) setMentions((prev) => [...prev, m])
    setMentionInput('')
  }

  const autoFillPrime = () => {
    const cells: ScheduleCell[] = []
    let c = 0
    for (let day = 0; day < 7; day++) {
      for (const hour of primeHours) {
        c++
        cells.push({ day, hour, postId: `auto-${c}` })
      }
    }
    setSchedule(cells)
    toast.success(`Auto-filled ${cells.length} prime time slots`)
  }

  const saveSchedule = async () => {
    try {
      await api.post('/api/v1/schedule/save', { slots: schedule })
      toast.success('Schedule saved')
    } catch (err) { toast.danger((err as Error).message) }
  }

  const assignCell = async (day: number, hour: number) => {
    if (!selectedDevice) return
    try {
      await api.post('/api/v1/schedule/assign', {
        post_id: `post-${day}-${hour}`,
        device_serial: selectedDevice.id,
        platform: selectedPlatform,
        scheduled_at: `${DAYS_OF_WEEK[day]} ${hour.toString().padStart(2, '0')}:00`,
      })
      setSchedule((prev) => [...prev, { day, hour, postId: `post-${day}-${hour}` }])
    } catch (err) { toast.danger((err as Error).message) }
  }

  const cancelPost = async (postId: number) => {
    try {
      await api.delete(`/api/v1/schedule/posts/${postId}`)
      toast.success('Post cancelled')
      fetchPosts()
    } catch { toast.danger('Failed to cancel') }
  }

  const retryPost = async (postId: number) => {
    try {
      await api.post(`/api/v1/schedule/posts/${postId}/retry`)
      toast.success('Post queued for retry')
      fetchPosts()
    } catch { toast.danger('Failed to retry') }
  }

  const refetchPlatforms = () => {
    if (selectedDevice) {
      api.get(`/api/v1/devices/${selectedDevice.id}/platforms?force=true`)
        .then((r) => {
          const data = r.data as PlatformInfo[]
          setPlatforms(data)
          const installed = data.filter((p) => p.installed)
          if (installed.length > 0) setShowNoPlatforms(false)
          toast.success(`Found ${installed.length} platforms`)
        })
        .catch(() => toast.danger('Detection failed'))
    }
  }

  const isPrime = (hour: number) => primeHours.includes(hour)
  const hasPost = (day: number, hour: number) => schedule.some((c) => c.day === day && c.hour === hour)

  const calYear = calendarMonth.getFullYear()
  const calMonth = calendarMonth.getMonth()
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate()
  const firstDayOfWeek = (new Date(calYear, calMonth, 1).getDay() + 6) % 7
  const monthName = calendarMonth.toLocaleDateString('en', { month: 'long', year: 'numeric' })

  const toggleDate = (dateStr: string) => {
    setSelectedDates((prev) => prev.includes(dateStr) ? prev.filter((d) => d !== dateStr) : [...prev, dateStr])
  }
  const todayStr = new Date().toISOString().slice(0, 10)

  const installedPlatforms = platforms.filter((p) => p.installed)

  return (
    <motion.div
      className="flex h-full flex-col bg-[--bg-0]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {/* Header */}
      <div className="flex h-12 items-center gap-3 border-b border-[--line-1] bg-[--bg-1] px-4">
        <CalendarClock className="h-5 w-5 text-[--blue]" />
        <h2 className="text-sm font-semibold text-[--txt-1]">Scheduler</h2>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setViewMode('wizard')}
            className={cn('rounded px-3 py-1 text-xs', viewMode === 'wizard' ? 'bg-[--blue] text-white' : 'bg-[--bg-2] text-[--txt-2]')}
          >
            Wizard
          </button>
          <button
            type="button"
            onClick={() => setViewMode('posts')}
            className={cn('rounded px-3 py-1 text-xs', viewMode === 'posts' ? 'bg-[--blue] text-white' : 'bg-[--bg-2] text-[--txt-2]')}
          >
            <ClipboardList className="mr-1 inline h-3 w-3" />
            Scheduled Posts
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {/* ──── POSTS LIST VIEW ──── */}
        {viewMode === 'posts' && (
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <select
                value={postsFilter.platform}
                onChange={(e) => setPostsFilter((p) => ({ ...p, platform: e.target.value }))}
                className="rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-xs text-[--txt-1]"
              >
                <option value="">All Platforms</option>
                <option value="instagram">Instagram</option>
                <option value="tiktok">TikTok</option>
                <option value="threads">Threads</option>
                <option value="twitter">Twitter</option>
                <option value="facebook">Facebook</option>
              </select>
              <select
                value={postsFilter.status}
                onChange={(e) => setPostsFilter((p) => ({ ...p, status: e.target.value }))}
                className="rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-xs text-[--txt-1]"
              >
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="processing">Processing</option>
                <option value="published">Published</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <Button variant="secondary" size="sm" onClick={fetchPosts} leftIcon={<RefreshCw className="h-3 w-3" />}>
                Refresh
              </Button>
              <span className="ml-auto text-xs text-[--txt-3]">{postsTotal} total</span>
            </div>

            {posts.length === 0 ? (
              <div className="py-12 text-center text-sm text-[--txt-3]">No scheduled posts</div>
            ) : (
              <div className="space-y-2">
                {posts.map((p) => (
                  <div key={p.id} className="flex items-center gap-3 rounded-lg border border-[--line-1] bg-[--bg-1] p-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-[--txt-3]">{p.scheduled_at ? new Date(p.scheduled_at).toLocaleString() : '—'}</span>
                        <span className="text-[--txt-2]">{PLATFORM_ICONS[p.platform] || ''} {p.platform}</span>
                        <Badge variant={(STATUS_COLORS[p.status] || 'neutral') as any}>{p.status}</Badge>
                      </div>
                      {p.caption && <div className="mt-1 truncate text-xs text-[--txt-2]">{p.caption.slice(0, 80)}...</div>}
                      {p.last_error && <div className="mt-1 text-[10px] text-red-400">{p.last_error}</div>}
                    </div>
                    <div className="flex gap-1">
                      {p.status === 'failed' && (
                        <Button variant="ghost" size="sm" onClick={() => retryPost(p.id)} leftIcon={<RotateCcw className="h-3 w-3" />}>Retry</Button>
                      )}
                      {(p.status === 'pending' || p.status === 'failed') && (
                        <Button variant="ghost" size="sm" onClick={() => cancelPost(p.id)} leftIcon={<Trash2 className="h-3 w-3" />}>Cancel</Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ──── WIZARD VIEW ──── */}
        {viewMode === 'wizard' && (
          <>
            {/* Step breadcrumbs */}
            <div className="mb-4 flex items-center gap-1 text-xs text-[--txt-3]">
              {(['Device', 'Platform', 'Post', 'Date', 'Time'] as const).map((label, i) => (
                <span key={label}>
                  {i > 0 && <ChevronRight className="mx-0.5 inline h-3 w-3" />}
                  <button
                    type="button"
                    onClick={() => goToStep((i + 1) as any)}
                    className={cn('text-xs', step >= (i + 1) ? 'font-medium text-[--txt-1]' : 'text-[--txt-3]')}
                  >
                    {label}
                  </button>
                </span>
              ))}
            </div>

            {/* STEP 1 — Device */}
            {step === 1 && (
              <div>
                <h3 className="mb-4 text-sm font-medium text-[--txt-1]">Select Device</h3>
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
                  {deviceList.map((d) => {
                    const isOnline = d.status === 'online'
                    return (
                      <button
                        key={d.id}
                        type="button"
                        onClick={() => isOnline && onSelectDevice(d)}
                        disabled={!isOnline}
                        className={cn(
                          'flex flex-col gap-1 rounded-lg border p-4 text-left transition-all',
                          !isOnline && 'cursor-not-allowed opacity-40',
                          'border-[--line-1] bg-[--bg-1] hover:border-[--blue] hover:bg-[--bg-2]',
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <Smartphone className="h-4 w-4 text-[--txt-2]" />
                          <span className="truncate text-sm font-medium text-[--txt-1]">{d.name}</span>
                        </div>
                        <div className="text-[10px] text-[--txt-3]">{d.phone_number ?? d.id.slice(0, 12)}</div>
                        <Badge variant={isOnline ? 'success' : 'neutral'} className="mt-1 text-[9px]">{d.status}</Badge>
                      </button>
                    )
                  })}
                  {deviceList.length === 0 && (
                    <div className="col-span-full py-6">
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
                </div>
              </div>
            )}

            {/* STEP 2 — Platform */}
            {step === 2 && (
              <div>
                <Button variant="ghost" size="sm" onClick={() => setStep(1)} leftIcon={<ArrowLeft className="h-3 w-3" />}>Back</Button>
                <h3 className="mb-4 mt-3 text-sm font-medium text-[--txt-1]">
                  Select Platform — {selectedDevice?.name}
                </h3>

                {showNoPlatforms ? (
                  <>
                    <NoPlatformsError
                      serial={selectedDevice?.id || ''}
                      onRetry={refetchPlatforms}
                      onConnect={() => selectedDevice && api.post(`/api/v1/agent/install/${selectedDevice.id}`).catch(() => {})}
                    />
                    <DeviceSetupPanel
                      serial={selectedDevice?.id || null}
                      compact
                      onComplete={() => {
                        setShowNoPlatforms(false)
                        refetchPlatforms()
                      }}
                    />
                  </>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                      {platforms.map((p) => (
                        <button
                          key={p.platform}
                          type="button"
                          onClick={() => p.installed && setSelectedPlatform(p.platform)}
                          disabled={!p.installed}
                          className={cn(
                            'rounded-lg border p-4 text-left transition-all',
                            !p.installed && 'cursor-not-allowed opacity-30',
                            selectedPlatform === p.platform
                              ? 'border-[--blue] bg-[--blue-glow]'
                              : 'border-[--line-1] bg-[--bg-1] hover:bg-[--bg-2]',
                          )}
                        >
                          <div className="text-sm font-medium text-[--txt-1]">
                            {PLATFORM_ICONS[p.platform] || ''} {p.name || p.platform}
                          </div>
                          <div className="text-[10px] text-[--txt-3]">
                            {p.installed ? `v${p.version || '?'}` : 'Not installed'}
                          </div>
                        </button>
                      ))}
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <Button variant="secondary" size="sm" onClick={refetchPlatforms} leftIcon={<RefreshCw className="h-3 w-3" />}>
                        Refresh Platforms
                      </Button>
                      <span className="text-[10px] text-[--txt-3]">
                        {installedPlatforms.length} of {platforms.length} available
                      </span>
                    </div>
                    {selectedPlatform && (
                      <div className="mt-4">
                        <Button variant="primary" onClick={() => goToStep(3)}>Next</Button>
                      </div>
                    )}
                    {!selectedPlatform && installedPlatforms.length > 0 && (
                      <p className="mt-2 text-xs text-amber-400">Select at least 1 platform to proceed</p>
                    )}
                  </>
                )}
              </div>
            )}

            {/* STEP 3 — Post Setup */}
            {step === 3 && (
              <div>
                <Button variant="ghost" size="sm" onClick={() => setStep(2)} leftIcon={<ArrowLeft className="h-3 w-3" />}>Back</Button>
                <h3 className="mb-4 mt-3 text-sm font-medium text-[--txt-1]">Post Setup</h3>

                {schedulerAccounts.filter((a: any) => a.platform === selectedPlatform).length > 1 && (
                  <div className="mb-4">
                    <label className="mb-1 block text-xs font-medium text-[--txt-3]">Post as</label>
                    <select
                      value={schedulerSelectedAccount?.id ?? ''}
                      onChange={(e) => {
                        const acc = schedulerAccounts.find((a: any) => a.id === Number(e.target.value))
                        setSchedulerSelectedAccount(acc || null)
                      }}
                      className="rounded border border-[--line-2] bg-[--bg-2] px-3 py-1.5 text-xs text-[--txt-1]"
                    >
                      {schedulerAccounts
                        .filter((a: any) => a.platform === selectedPlatform)
                        .map((a: any) => (
                          <option key={a.id} value={a.id}>
                            @{a.username} {a.is_primary ? '(Primary)' : `(${a.clone_method || 'Clone'})`}
                          </option>
                        ))}
                    </select>
                  </div>
                )}

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <div className="space-y-4">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-[--txt-3]">Caption Tone</label>
                      <div className="flex flex-wrap gap-2">
                        {TONES.map((t) => (
                          <button key={t} type="button" onClick={() => setCaptionTone(t)} className={cn(
                            'rounded-md px-3 py-1 text-xs font-medium transition-all',
                            captionTone === t ? 'bg-[--blue] text-white' : 'bg-[--bg-2] text-[--txt-2] hover:bg-[--bg-3]',
                          )}>{t}</button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="mb-1 flex items-center gap-2">
                        <label className="text-xs font-medium text-[--txt-3]">Caption</label>
                        <Button variant="secondary" size="sm" onClick={generateCaption}>Generate</Button>
                      </div>
                      <textarea
                        value={caption}
                        onChange={(e) => setCaption(e.target.value)}
                        rows={4}
                        className="w-full rounded-md border border-[--line-2] bg-[--bg-2] px-3 py-2 text-sm text-[--txt-1]"
                        placeholder="Write or generate a caption..."
                      />
                      <div className="mt-1 text-[10px] text-[--txt-3]">{caption.length} / 2200 characters</div>
                    </div>

                    <div>
                      <label className="mb-1 block text-xs font-medium text-[--txt-3]">Posts Per Day</label>
                      <input type="number" min={1} max={10} value={postsPerDay} onChange={(e) => setPostsPerDay(Number(e.target.value))} className="w-20 rounded-md border border-[--line-2] bg-[--bg-2] px-3 py-1.5 text-sm text-[--txt-1]" />
                    </div>
                  </div>

                  <div className="space-y-4">
                    {/* Hashtags */}
                    <div>
                      <label className="mb-1 block text-xs font-medium text-[--txt-3]">Hashtags</label>
                      <div className="flex gap-1">
                        <input value={hashtagInput} onChange={(e) => setHashtagInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addHashtag())} placeholder="#hashtag" className="flex-1 rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-xs text-[--txt-1]" />
                        <Button variant="secondary" size="sm" onClick={addHashtag}>Add</Button>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {hashtags.map((h) => (
                          <span key={h} className="flex items-center gap-1 rounded-full bg-[--blue-glow] px-2 py-0.5 text-[10px] text-[--blue]">
                            {h}
                            <button type="button" onClick={() => setHashtags((prev) => prev.filter((t) => t !== h))}><X className="h-2.5 w-2.5" /></button>
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Location */}
                    <div>
                      <label className="mb-1 block text-xs font-medium text-[--txt-3]">Location</label>
                      <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Add location" className="w-full rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-xs text-[--txt-1]" />
                    </div>

                    {/* Mentions */}
                    <div>
                      <label className="mb-1 block text-xs font-medium text-[--txt-3]">Mentions</label>
                      <div className="flex gap-1">
                        <input value={mentionInput} onChange={(e) => setMentionInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addMention())} placeholder="@username" className="flex-1 rounded border border-[--line-2] bg-[--bg-2] px-2 py-1 text-xs text-[--txt-1]" />
                        <Button variant="secondary" size="sm" onClick={addMention}>Add</Button>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {mentions.map((m) => (
                          <span key={m} className="flex items-center gap-1 rounded-full bg-violet-500/10 px-2 py-0.5 text-[10px] text-violet-400">
                            {m}
                            <button type="button" onClick={() => setMentions((prev) => prev.filter((t) => t !== m))}><X className="h-2.5 w-2.5" /></button>
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Save Draft */}
                    <Button variant="secondary" size="sm" onClick={async () => {
                      try {
                        await api.post('/api/v1/posts/draft', { caption, tone: captionTone, hashtags, location, mentions })
                        toast.success('Draft saved')
                      } catch { toast.danger('Failed to save draft') }
                    }}>Save Draft</Button>
                  </div>
                </div>

                <div className="mt-4">
                  <Button variant="primary" onClick={() => goToStep(4)}>Next — Choose Date</Button>
                </div>
              </div>
            )}

            {/* STEP 4 — Calendar */}
            {step === 4 && (
              <div>
                <Button variant="ghost" size="sm" onClick={() => setStep(3)} leftIcon={<ArrowLeft className="h-3 w-3" />}>Back</Button>
                <h3 className="mb-4 mt-3 text-sm font-medium text-[--txt-1]">Choose Date</h3>

                <div className="mb-3 flex items-center gap-3">
                  <button type="button" onClick={() => setCalendarMonth(new Date(calYear, calMonth - 1))} className="rounded p-1 hover:bg-[--bg-2]">
                    <ChevronLeft className="h-4 w-4 text-[--txt-2]" />
                  </button>
                  <span className="min-w-[140px] text-center text-sm font-medium text-[--txt-1]">{monthName}</span>
                  <button type="button" onClick={() => setCalendarMonth(new Date(calYear, calMonth + 1))} className="rounded p-1 hover:bg-[--bg-2]">
                    <ChevronRight className="h-4 w-4 text-[--txt-2]" />
                  </button>
                </div>

                <div className="mb-2 flex gap-2">
                  {[
                    { label: 'Today', fn: () => toggleDate(todayStr) },
                    { label: 'Tomorrow', fn: () => { const d = new Date(); d.setDate(d.getDate() + 1); toggleDate(d.toISOString().slice(0, 10)) } },
                    { label: 'Weekend', fn: () => {
                      const d = new Date(); const sat = new Date(d); sat.setDate(d.getDate() + (6 - d.getDay()))
                      const sun = new Date(sat); sun.setDate(sat.getDate() + 1)
                      toggleDate(sat.toISOString().slice(0, 10)); toggleDate(sun.toISOString().slice(0, 10))
                    }},
                  ].map((q) => (
                    <button key={q.label} type="button" onClick={q.fn} className="rounded-md bg-[--bg-2] px-3 py-1 text-xs text-[--txt-2] hover:bg-[--bg-3]">{q.label}</button>
                  ))}
                </div>

                <div className="grid grid-cols-7 gap-1">
                  {DAYS_OF_WEEK.map((d) => <div key={d} className="py-1 text-center text-[10px] font-medium text-[--txt-3]">{d}</div>)}
                  {Array.from({ length: firstDayOfWeek }).map((_, i) => <div key={`pad-${i}`} />)}
                  {Array.from({ length: daysInMonth }).map((_, i) => {
                    const day = i + 1
                    const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                    const selected = selectedDates.includes(dateStr)
                    const isToday = dateStr === todayStr
                    return (
                      <button key={day} type="button" onClick={() => toggleDate(dateStr)} className={cn(
                        'rounded-md py-2 text-center text-xs transition-all',
                        selected ? 'bg-[--blue] font-medium text-white' : isToday ? 'bg-[--bg-2] font-medium text-[--blue]' : 'text-[--txt-2] hover:bg-[--bg-2]',
                      )}>{day}</button>
                    )
                  })}
                </div>

                {selectedDates.length > 0 && <div className="mt-3 text-xs text-[--txt-3]">Selected: {selectedDates.length} date(s)</div>}
                <div className="mt-4"><Button variant="primary" onClick={() => goToStep(5)}>Next — Choose Time</Button></div>
              </div>
            )}

            {/* STEP 5 — Time Grid */}
            {step === 5 && (
              <div>
                <div className="flex items-center justify-between">
                  <Button variant="ghost" size="sm" onClick={() => setStep(4)} leftIcon={<ArrowLeft className="h-3 w-3" />}>Back</Button>
                  <div className="flex items-center gap-2">
                    {REGIONS.map((r) => (
                      <button key={r} type="button" onClick={() => setRegion(r)} className={cn(
                        'rounded-md px-3 py-1 text-xs font-medium transition-all',
                        region === r ? 'bg-[--blue] text-white' : 'bg-[--bg-2] text-[--txt-2] hover:bg-[--bg-3]',
                      )}>{r.toUpperCase()}</button>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={autoFillPrime} leftIcon={<Sparkles className="h-3 w-3" />}>Auto-fill Prime</Button>
                    <Button variant="primary" size="sm" onClick={saveSchedule}>Save Schedule</Button>
                  </div>
                </div>

                <div className="mt-4 overflow-auto">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr>
                        <th className="sticky left-0 w-16 bg-[--bg-0] py-2 text-xs text-[--txt-3]" />
                        {HOURS.map((h) => <th key={h} className="min-w-[48px] py-2 text-center text-[10px] text-[--txt-3]">{h.toString().padStart(2, '0')}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {DAYS_OF_WEEK.map((day, dayIdx) => (
                        <tr key={day}>
                          <td className="sticky left-0 bg-[--bg-0] py-1 text-xs font-medium text-[--txt-2]">{day}</td>
                          {HOURS.map((hour) => {
                            const prime = isPrime(hour)
                            const filled = hasPost(dayIdx, hour)
                            return (
                              <td key={hour} className="p-0.5">
                                <button type="button" onClick={() => !filled && assignCell(dayIdx, hour)} className={cn(
                                  'flex h-8 w-full items-center justify-center rounded text-[10px] transition-all',
                                  filled ? 'bg-[--blue]/60 text-white' : prime ? 'bg-[--green]/20 text-[--green] hover:bg-[--green]/40' : 'bg-[--bg-2] text-[--txt-3] hover:bg-[--bg-3]',
                                )}>{filled ? 'P' : prime ? '*' : ''}</button>
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {showFixWizard && selectedDevice && (
        <FixEverythingWizard
          serial={selectedDevice.id}
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
