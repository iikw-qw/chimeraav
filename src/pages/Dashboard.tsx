import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend,
} from 'recharts'
import {
  Flame, Heart, MonitorSmartphone, CalendarClock, Zap, Activity, Wrench,
} from 'lucide-react'
import { api } from '../api/client'
import { useDevices, type Device } from '../hooks/useDevices'
import { useAccounts, type AccountRow } from '../hooks/useAccounts'
import { Button } from '../components/ui'
import { toast } from '../hooks/useToast'

const pageMotion = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.18 } }

function StatCard({ title, value, sub, color, icon: Icon }: {
  title: string; value: string | number; sub?: string; color: string
  icon?: typeof Flame
}) {
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5">
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`h-4 w-4 ${color}`} />}
        <p className="text-xs uppercase tracking-wider text-[--txt-3]">{title}</p>
      </div>
      <p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-[--txt-3]">{sub}</p>}
    </div>
  )
}

const STATUS_COLORS: Record<string, string> = {
  online: '#22c55e', offline: '#6b7280', busy: '#eab308', error: '#ef4444', paused: '#8b5cf6',
}

export function Dashboard() {
  const { data: devices = [] } = useDevices()
  const { data: accounts = [] } = useAccounts()

  const { data: taskStats } = useQuery({
    queryKey: ['dashboard', 'task-stats'],
    queryFn: async () => {
      try { return (await api.get('/api/tasks/stats')).data } catch { return { pending: 0, running: 0, completed: 0, failed: 0 } }
    },
    refetchInterval: 10_000,
  })

  const { data: dailyStats } = useQuery({
    queryKey: ['dashboard', 'daily-stats'],
    queryFn: async () => {
      try { return (await api.get('/api/v1/stats/daily')).data } catch { return { posts: 0, likes: 0, warmup_sessions: 0, active_warmups: 0 } }
    },
    refetchInterval: 10_000,
  })

  const { data: warmupHistory } = useQuery({
    queryKey: ['dashboard', 'warmup-history'],
    queryFn: async () => {
      try {
        const r = await api.get('/api/v1/stats/warmup-history?days=7')
        const raw = (r.data as { data?: Record<string, { scrolls: number; likes: number; profiles: number; stories: number }> }).data ?? {}
        return Object.entries(raw).map(([day, v]) => ({ day, ...v }))
      } catch { return [] }
    },
    refetchInterval: 30_000,
  })

  const { data: upcomingPosts } = useQuery({
    queryKey: ['dashboard', 'upcoming'],
    queryFn: async () => {
      try { return (await api.get('/api/v1/schedule/upcoming?limit=5')).data } catch { return [] }
    },
    refetchInterval: 15_000,
  })

  const { data: systemInfo } = useQuery({
    queryKey: ['dashboard', 'system-info'],
    queryFn: async () => {
      try { return (await api.get('/api/dashboard/system-info')).data } catch { return null }
    },
    refetchInterval: 15_000,
  })

  const deviceList: Device[] = Array.isArray(devices) ? devices : []
  const accountList: AccountRow[] = Array.isArray(accounts) ? accounts : []
  const online = deviceList.filter((d) => d.status === 'online').length
  const activeAccounts = accountList.filter((a) => a.status === 'active').length

  const deviceStatusData = Object.entries(
    deviceList.reduce<Record<string, number>>((acc, d) => {
      const s = d.status || 'offline'
      acc[s] = (acc[s] || 0) + 1
      return acc
    }, {}),
  ).map(([name, value]) => ({ name, value, fill: STATUS_COLORS[name] || '#6b7280' }))

  const platformData = Object.entries(
    accountList.reduce<Record<string, number>>((acc, a) => {
      const p = a.platform || 'other'
      acc[p] = (acc[p] || 0) + 1
      return acc
    }, {}),
  ).map(([name, value]) => ({ name, value }))

  const PLATFORM_COLORS = ['#E4405F', '#0088CC', '#1877F2', '#FE2C55', '#000', '#0A66C2', '#4C75A3', '#FF0000', '#FF4500', '#666']

  const startAllWarmups = async () => {
    try {
      await api.post('/api/v1/warmup/start-all', { platforms: ['instagram'], intensity: 5, mode: 'single' })
      toast.success('Warmup started on all devices')
    } catch { toast.danger('Failed to start warmups') }
  }

  const stopAllWarmups = async () => {
    try {
      await api.post('/api/v1/warmup/stop-all')
      toast.success('All warmups stopped')
    } catch { toast.danger('Failed to stop warmups') }
  }

  return (
    <motion.div {...pageMotion} className="h-full overflow-y-auto p-6">
      <h1 className="mb-6 text-xl font-semibold text-[--txt-1]">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard title="Devices Online" value={`${online}/${deviceList.length}`} icon={MonitorSmartphone} color="text-emerald-400" />
        <StatCard title="Active Warmups" value={dailyStats?.active_warmups ?? 0} icon={Flame} color="text-amber-400" />
        <StatCard title="Scheduled Posts" value={Array.isArray(upcomingPosts) ? upcomingPosts.length : 0} icon={CalendarClock} color="text-blue-400" />
        <StatCard title="Likes Today" value={dailyStats?.likes ?? 0} icon={Heart} color="text-red-400" />
      </div>

      {/* Quick Actions */}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" size="sm" onClick={startAllWarmups} leftIcon={<Flame className="h-3.5 w-3.5" />}>
          Start All Warmups
        </Button>
        <Button variant="secondary" size="sm" onClick={stopAllWarmups}>
          Stop All
        </Button>
        <Button variant="secondary" size="sm" onClick={() => api.post('/api/v1/datasets/sync-to-device', { serial: 'all', path: '' }).catch(() => {})}>
          Sync Datasets
        </Button>
        <Button variant="secondary" size="sm" onClick={async () => {
          try {
            const r = await api.post('/api/v1/devices/fix-all')
            const results = r.data as any[]
            const ok = results.filter((r: any) => r.success).length
            toast.success(`Fixed ${ok}/${results.length} device(s)`)
          } catch { toast.danger('Fix all failed') }
        }} leftIcon={<Wrench className="h-3.5 w-3.5" />}>
          Fix All Devices
        </Button>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Warmup Chart */}
        {Array.isArray(warmupHistory) && warmupHistory.length > 0 && (
          <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5">
            <h2 className="mb-4 text-sm font-medium text-[--txt-2]">Warmup Activity (7 days)</h2>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={warmupHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="day" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, color: '#f1f5f9' }} />
                <Legend />
                <Line type="monotone" dataKey="scrolls" stroke="#3b82f6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="likes" stroke="#ef4444" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="profiles" stroke="#8b5cf6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="stories" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Upcoming Posts */}
        {Array.isArray(upcomingPosts) && upcomingPosts.length > 0 && (
          <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5">
            <h2 className="mb-4 text-sm font-medium text-[--txt-2]">Upcoming Posts</h2>
            <div className="space-y-2">
              {(upcomingPosts as any[]).map((p: any, i: number) => (
                <div key={i} className="flex items-center justify-between rounded-lg bg-white/[0.02] px-3 py-2 text-xs">
                  <span className="text-[--txt-1]">{p.platform}</span>
                  <span className="text-[--txt-3]">{p.scheduled_at}</span>
                  <span className="text-[--txt-3]">{p.caption_preview}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {deviceStatusData.length > 0 && (
          <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5">
            <h2 className="mb-4 text-sm font-medium text-[--txt-2]">Devices by Status</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={deviceStatusData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, color: '#f1f5f9' }} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {deviceStatusData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {platformData.length > 0 && (
          <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5">
            <h2 className="mb-4 text-sm font-medium text-[--txt-2]">Accounts by Platform</h2>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={platformData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {platformData.map((_, i) => <Cell key={i} fill={PLATFORM_COLORS[i % PLATFORM_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, color: '#f1f5f9' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {systemInfo && (
          <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5">
            <h2 className="mb-4 text-sm font-medium text-[--txt-2]">Server</h2>
            <div className="space-y-3">
              {[
                { label: 'CPU', value: systemInfo.cpu_percent, color: 'bg-blue-500' },
                { label: 'RAM', value: systemInfo.ram_percent, color: 'bg-emerald-500' },
                { label: 'Disk', value: systemInfo.disk_percent, color: 'bg-amber-500' },
              ].map(({ label, value, color }) => (
                <div key={label}>
                  <div className="mb-1 flex justify-between text-xs text-[--txt-3]">
                    <span>{label}</span><span>{value ?? 0}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5">
                    <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(value ?? 0, 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
