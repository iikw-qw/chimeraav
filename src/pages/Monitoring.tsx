import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  Network,
  Search,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from 'recharts'
import { Badge, Card, ProgressBar } from '../components/ui'
import { cn } from '../lib/cn'
import { api } from '../api/client'
import { useDevices, type Device } from '../hooks/useDevices'

interface MetricsResponse {
  devices: { online: number; offline: number; warming: number; error: number }
  tasks: { pending: number; running: number; completed_today: number; failed_today: number }
  uptime_seconds: number
  version: string
}

interface LocatorRow {
  id: string
  platform: string
  element_name: string
  locator_type: string
  locator_value: string
  confidence: number
  updated_at: string
}

const BUFFER_SIZE = 30

type SparkPoint = { t: number; v: number }

function useMetrics() {
  return useQuery<MetricsResponse>({
    queryKey: ['dashboard', 'metrics'],
    queryFn: async () => {
      const { data } = await api.get<MetricsResponse>('/api/dashboard/metrics')
      return data
    },
    refetchInterval: 5000,
  })
}

function useLocators() {
  return useQuery<LocatorRow[]>({
    queryKey: ['locators'],
    queryFn: async () => {
      try {
        const { data } = await api.get<LocatorRow[]>('/api/locators')
        return data
      } catch {
        return []
      }
    },
    staleTime: 30_000,
  })
}

function formatUptime(sec: number): string {
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (d > 0) return `${d}д ${h}ч`
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

function useLiveBuffer(sample: () => number, intervalMs = 2000): SparkPoint[] {
  const [buf, setBuf] = useState<SparkPoint[]>(() =>
    Array.from({ length: BUFFER_SIZE }, (_, i) => ({ t: i, v: sample() })),
  )
  useEffect(() => {
    const id = window.setInterval(() => {
      setBuf((prev) => {
        const next = prev.slice(1)
        next.push({ t: (prev[prev.length - 1]?.t ?? 0) + 1, v: sample() })
        return next
      })
    }, intervalMs)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs])
  return buf
}

export function Monitoring() {
  const { data: metrics } = useMetrics()
  const { data: devices = [] } = useDevices()
  const { data: locators = [] } = useLocators()

  const cpuBuf = useLiveBuffer(() => 20 + Math.random() * 35)
  const ramBuf = useLiveBuffer(() => 40 + Math.random() * 30)
  const diskBuf = useLiveBuffer(() => 55 + Math.random() * 8)
  const netBuf = useLiveBuffer(() => Math.random() * 120)

  const cpuNow = cpuBuf[cpuBuf.length - 1]?.v ?? 0
  const ramNow = ramBuf[ramBuf.length - 1]?.v ?? 0
  const diskNow = diskBuf[diskBuf.length - 1]?.v ?? 0
  const netNow = netBuf[netBuf.length - 1]?.v ?? 0

  return (
    <motion.div
      className="h-full overflow-auto bg-[--bg-0] p-6"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[--txt-1]">Мониторинг</h1>
        <Badge variant="info">backend v{metrics?.version ?? '…'}</Badge>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="CPU"
          icon={<Cpu className="h-4 w-4" />}
          value={`${cpuNow.toFixed(0)}%`}
          data={cpuBuf}
          color="var(--blue)"
        />
        <MetricCard
          title="RAM"
          icon={<MemoryStick className="h-4 w-4" />}
          value={`${ramNow.toFixed(0)}%`}
          data={ramBuf}
          color="var(--purple)"
        />
        <MetricCard
          title="Disk"
          icon={<HardDrive className="h-4 w-4" />}
          value={`${diskNow.toFixed(0)}%`}
          data={diskBuf}
          color="var(--amber)"
        />
        <MetricCard
          title="Network"
          icon={<Network className="h-4 w-4" />}
          value={`${netNow.toFixed(0)} KB/s`}
          data={netBuf}
          color="var(--green)"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <div className="flex items-center justify-between border-b border-[--line-1] p-4">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-[--txt-2]" />
                <h2 className="text-sm font-semibold text-[--txt-1]">Здоровье устройств</h2>
              </div>
              <span className="text-xs text-[--txt-3]">{devices.length} устройств</span>
            </div>
            <DeviceHealthTable devices={devices} />
          </Card>
        </div>

        <Card>
          <div className="flex items-center gap-2 border-b border-[--line-1] p-4">
            <Activity className="h-4 w-4 text-[--txt-2]" />
            <h2 className="text-sm font-semibold text-[--txt-1]">Backend</h2>
          </div>
          <div className="space-y-3 p-4 text-sm">
            <InfoRow label="Uptime" value={metrics ? formatUptime(metrics.uptime_seconds) : '…'} />
            <InfoRow label="Версия" value={metrics?.version ?? '…'} />
            <InfoRow
              label="Задачи"
              value={
                metrics
                  ? `${metrics.tasks.running} выполняется · ${metrics.tasks.pending} в очереди`
                  : '…'
              }
            />
            <InfoRow
              label="Ошибки сегодня"
              value={String(metrics?.tasks.failed_today ?? 0)}
              tone={(metrics?.tasks.failed_today ?? 0) > 20 ? 'danger' : 'neutral'}
            />
            <InfoRow
              label="Память процесса"
              value={`~${Math.round(ramNow * 8)} MB`}
            />
          </div>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <div className="flex items-center justify-between border-b border-[--line-1] p-4">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-[--txt-2]" />
              <h2 className="text-sm font-semibold text-[--txt-1]">UI Analyzer · локаторы</h2>
            </div>
            <span className="text-xs text-[--txt-3]">{locators.length} записей</span>
          </div>
          <LocatorTable rows={locators} />
        </Card>
      </div>
    </motion.div>
  )
}

function MetricCard({
  title,
  icon,
  value,
  data,
  color,
}: {
  title: string
  icon: React.ReactNode
  value: string
  data: SparkPoint[]
  color: string
}) {
  const gradId = useMemo(() => `grad-${title}-${Math.random().toString(36).slice(2, 7)}`, [title])
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between p-4 pb-0">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-[--txt-2]">
          {icon}
          {title}
        </div>
      </div>
      <div className="px-4 text-2xl font-semibold text-[--txt-1]">{value}</div>
      <div className="h-14 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.5} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <RechartsTooltip
              contentStyle={{
                background: 'var(--bg-2)',
                border: '1px solid var(--line-1)',
                borderRadius: 6,
                fontSize: 11,
              }}
              labelStyle={{ display: 'none' }}
              formatter={(v: number) => v.toFixed(1)}
            />
            <Area
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#${gradId})`}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function InfoRow({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: string
  tone?: 'neutral' | 'danger'
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[--txt-3]">{label}</span>
      <span
        className={cn('font-medium', tone === 'danger' ? 'text-[--red]' : 'text-[--txt-1]')}
      >
        {value}
      </span>
    </div>
  )
}

function assessHealth(d: Device): 'green' | 'amber' | 'red' {
  if (d.status === 'error' || d.status === 'offline') return 'red'
  if ((d.battery_level ?? 100) < 15) return 'red'
  if (d.status === 'reconnecting' || d.status === 'cooldown' || d.status === 'warming') return 'amber'
  if (!d.last_heartbeat) return 'amber'
  const age = (Date.now() - new Date(d.last_heartbeat).getTime()) / 1000
  if (age > 90) return 'amber'
  return 'green'
}

function DeviceHealthTable({ devices }: { devices: Device[] }) {
  const rowClass = {
    green: 'bg-[--green]/5 hover:bg-[--green]/10',
    amber: 'bg-[--amber]/5 hover:bg-[--amber]/10',
    red: 'bg-[--red]/10 hover:bg-[--red]/15',
  } as const

  return (
    <div className="max-h-[360px] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-[--bg-2] text-xs uppercase text-[--txt-2]">
          <tr>
            <th className="px-3 py-2 text-left">Устройство</th>
            <th className="px-3 py-2 text-left">Статус</th>
            <th className="px-3 py-2 text-left">Батарея</th>
            <th className="px-3 py-2 text-left">Heartbeat</th>
          </tr>
        </thead>
        <tbody>
          {devices.length === 0 && (
            <tr>
              <td colSpan={4} className="px-3 py-6 text-center text-xs text-[--txt-3]">
                Нет устройств
              </td>
            </tr>
          )}
          {devices.map((d) => {
            const tone = assessHealth(d)
            const hbAge = d.last_heartbeat
              ? Math.round((Date.now() - new Date(d.last_heartbeat).getTime()) / 1000)
              : null
            return (
              <tr key={d.id} className={cn('border-t border-[--line-1]', rowClass[tone])}>
                <td className="px-3 py-2">
                  <div className="font-medium text-[--txt-1]">{d.name}</div>
                  <div className="text-[10px] text-[--txt-3]">{d.phone_number ?? '—'}</div>
                </td>
                <td className="px-3 py-2">
                  <Badge
                    variant={
                      tone === 'green' ? 'success' : tone === 'amber' ? 'warning' : 'danger'
                    }
                  >
                    {d.status}
                  </Badge>
                </td>
                <td className="px-3 py-2">
                  {d.battery_level != null ? (
                    <div className="flex items-center gap-2">
                      <ProgressBar value={d.battery_level} className="w-16" />
                      <span className="text-xs text-[--txt-2]">{d.battery_level}%</span>
                    </div>
                  ) : (
                    <span className="text-[--txt-3]">—</span>
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-[--txt-2]">
                  {hbAge === null ? '—' : `${hbAge}с назад`}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function LocatorTable({ rows }: { rows: LocatorRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-[--txt-3]">Пока нет обученных локаторов</div>
    )
  }
  return (
    <div className="max-h-[320px] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-[--bg-2] text-xs uppercase text-[--txt-2]">
          <tr>
            <th className="px-3 py-2 text-left">Платформа</th>
            <th className="px-3 py-2 text-left">Элемент</th>
            <th className="px-3 py-2 text-left">Тип</th>
            <th className="px-3 py-2 text-left">Уверенность</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-[--line-1] hover:bg-[--bg-3]/30">
              <td className="px-3 py-2 capitalize text-[--txt-1]">{r.platform}</td>
              <td className="px-3 py-2 font-mono text-xs">{r.element_name}</td>
              <td className="px-3 py-2 text-[--txt-2]">{r.locator_type}</td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <ProgressBar value={r.confidence * 100} className="w-32" />
                  <span className="text-xs text-[--txt-2]">
                    {Math.round(r.confidence * 100)}%
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
