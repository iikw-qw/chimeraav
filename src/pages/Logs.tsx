import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronDown, ChevronRight, Download, Filter, Search } from 'lucide-react'
import { FixedSizeList, type ListChildComponentProps } from 'react-window'
import { useQuery } from '@tanstack/react-query'
import { Badge, Input, Switch } from '../components/ui'
import { cn } from '../lib/cn'
import { api } from '../api/client'
import { ws } from '../api/ws'
import { useDevices } from '../hooks/useDevices'

interface LogEntry {
  id: string
  created_at: string
  level: 'info' | 'warning' | 'error' | 'debug' | string
  device_id?: string | null
  action_type: string
  details?: Record<string, unknown> | string | null
}

type LevelFilter = 'all' | 'info' | 'warning' | 'error'

const LEVELS: Array<{ key: LevelFilter; label: string }> = [
  { key: 'all', label: 'Все' },
  { key: 'info', label: 'Info' },
  { key: 'warning', label: 'Warning' },
  { key: 'error', label: 'Error' },
]

const CATEGORIES: Array<{ key: string; label: string; prefixes: string[] }> = [
  { key: 'all', label: 'Все', prefixes: [] },
  { key: 'device', label: 'Устройства', prefixes: ['device_', 'autostart_', 'stop_', 'restart_'] },
  { key: 'tunnel', label: 'Туннели', prefixes: ['tunnel_'] },
  { key: 'wda', label: 'WDA', prefixes: ['wda_'] },
  { key: 'cleanup', label: 'Очистка', prefixes: ['cleanup_', 'port_'] },
  { key: 'pairing', label: 'Сопряжение', prefixes: ['supervised_pair', 'image_mount'] },
  { key: 'alert', label: 'Alert Watcher', prefixes: ['alert_watcher_'] },
  { key: 'ocr', label: 'OCR', prefixes: ['ocr_'] },
  { key: 'ui', label: 'UI', prefixes: ['ui_'] },
  { key: 'telegram', label: 'Telegram', prefixes: ['telegram_'] },
  { key: 'settings', label: 'Настройки', prefixes: ['settings_'] },
  { key: 'other', label: 'Прочее', prefixes: [] },
]

function matchesCategory(actionType: string, categoryKey: string): boolean {
  if (categoryKey === 'all') return true
  const cat = CATEGORIES.find((c) => c.key === categoryKey)
  if (!cat) return true
  if (categoryKey === 'other') {
    return !CATEGORIES.some(
      (c) =>
        c.key !== 'all' &&
        c.key !== 'other' &&
        c.prefixes.some((p) => actionType.startsWith(p)),
    )
  }
  return cat.prefixes.some((p) => actionType.startsWith(p))
}

const ROW_HEIGHT = 28

function useLogsHistory() {
  return useQuery<LogEntry[]>({
    queryKey: ['logs', 'history'],
    queryFn: async () => {
      try {
        const { data } = await api.get<LogEntry[]>('/api/logs', { params: { limit: 500 } })
        return data
      } catch {
        return []
      }
    },
    staleTime: 15_000,
  })
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('ru-RU', { hour12: false })
  } catch {
    return '--:--:--'
  }
}

function levelColor(level: string): 'info' | 'warning' | 'danger' | 'neutral' {
  const l = level.toLowerCase()
  if (l === 'error' || l === 'critical') return 'danger'
  if (l === 'warning' || l === 'warn') return 'warning'
  if (l === 'info') return 'info'
  return 'neutral'
}

export function Logs() {
  const { data: history = [] } = useLogsHistory()
  const { data: devices = [] } = useDevices()

  const [entries, setEntries] = useState<LogEntry[]>([])
  const [level, setLevel] = useState<LevelFilter>('all')
  const [category, setCategory] = useState('all')
  const [deviceId, setDeviceId] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [showCategories, setShowCategories] = useState(false)
  const listRef = useRef<FixedSizeList>(null)

  useEffect(() => {
    if (history.length) setEntries(history)
  }, [history])

  useEffect(() => {
    const unsub = ws.subscribe('logs', (payload) => {
      const entry = payload as LogEntry
      if (!entry || !entry.id) return
      setEntries((prev) => {
        const next = [...prev, entry]
        return next.length > 2000 ? next.slice(-2000) : next
      })
    })
    return unsub
  }, [])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return entries.filter((e) => {
      if (level !== 'all' && e.level.toLowerCase() !== level) return false
      if (deviceId !== 'all' && e.device_id !== deviceId) return false
      if (!matchesCategory(e.action_type, category)) return false
      if (needle) {
        const hay = `${e.action_type} ${JSON.stringify(e.details ?? '')}`.toLowerCase()
        if (!hay.includes(needle)) return false
      }
      return true
    })
  }, [entries, level, deviceId, category, search])

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const cat of CATEGORIES) {
      counts[cat.key] =
        cat.key === 'all'
          ? entries.length
          : entries.filter((e) => matchesCategory(e.action_type, cat.key)).length
    }
    return counts
  }, [entries])

  useEffect(() => {
    if (autoScroll && listRef.current && filtered.length > 0) {
      listRef.current.scrollToItem(filtered.length - 1, 'end')
    }
  }, [filtered.length, autoScroll])

  const toggle = useCallback((id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))
  }, [])

  const exportCsv = () => {
    const header = 'timestamp,level,device_id,type,details\n'
    const rows = filtered
      .map((e) =>
        [
          e.created_at,
          e.level,
          e.device_id ?? '',
          e.action_type,
          JSON.stringify(e.details ?? ''),
        ]
          .map((c) => `"${String(c).replace(/"/g, '""')}"`)
          .join(','),
      )
      .join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const deviceName = (id: string | null | undefined) =>
    id ? devices.find((d) => d.id === id)?.name ?? id.slice(0, 8) : '—'

  const Row = useCallback(
    ({ index, style }: ListChildComponentProps) => {
      const e = filtered[index]
      const isOpen = !!expanded[e.id]
      return (
        <div
          style={style}
          onClick={() => toggle(e.id)}
          className={cn(
            'flex cursor-pointer items-center gap-2 px-3 font-mono text-xs transition-colors',
            'hover:bg-[--bg-3]/30',
          )}
        >
          <span className="w-3 text-[--txt-3]">
            {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </span>
          <span className="w-20 shrink-0 text-[--txt-3]">[{formatTime(e.created_at)}]</span>
          <span className="w-16 shrink-0">
            <Badge variant={levelColor(e.level)}>{e.level.toUpperCase()}</Badge>
          </span>
          <span className="w-28 shrink-0 truncate text-[--txt-2]">{deviceName(e.device_id)}</span>
          <span className="w-32 shrink-0 truncate text-[--blue]">{e.action_type}</span>
          <span className="flex-1 truncate text-[--txt-1]">
            {typeof e.details === 'string'
              ? e.details
              : e.details
                ? JSON.stringify(e.details)
                : ''}
          </span>
        </div>
      )
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filtered, expanded, devices],
  )

  const expandedEntries = filtered.filter((e) => expanded[e.id])

  return (
    <motion.div
      className="flex h-full flex-col bg-[--bg-0]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex h-14 shrink-0 items-center gap-3 border-b border-[--line-1] bg-[--bg-1] px-4">
        <div className="inline-flex rounded-lg border border-[--line-2] bg-[--bg-3] p-0.5">
          {LEVELS.map((l) => (
            <button
              key={l.key}
              type="button"
              onClick={() => setLevel(l.key)}
              className={cn(
                'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                level === l.key
                  ? 'bg-[--bg-1] text-[--txt-1] shadow-sm'
                  : 'text-[--txt-2] hover:text-[--txt-1]',
              )}
            >
              {l.label}
            </button>
          ))}
        </div>

        <select
          value={deviceId}
          onChange={(e) => setDeviceId(e.target.value)}
          className="h-9 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1] focus:border-[--blue] focus:outline-none"
        >
          <option value="all">Все устройства</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={() => setShowCategories((v) => !v)}
          className={cn(
            'inline-flex h-9 items-center gap-1.5 rounded-md border px-3 text-xs font-medium transition-colors',
            showCategories || category !== 'all'
              ? 'border-[--blue] bg-[--blue]/10 text-[--blue]'
              : 'border-[--line-2] bg-[--bg-3] text-[--txt-1] hover:bg-[--bg-2]',
          )}
        >
          <Filter className="h-3.5 w-3.5" />
          {category === 'all'
            ? 'Категория'
            : CATEGORIES.find((c) => c.key === category)?.label ?? category}
        </button>

        <div className="max-w-xs flex-1">
          <Input
            leftIcon={<Search className="h-3.5 w-3.5" />}
            placeholder="Поиск"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-2 text-xs text-[--txt-2]">
          <span>Автоскролл</span>
          <Switch checked={autoScroll} onChange={setAutoScroll} />
        </div>

        <button
          type="button"
          onClick={exportCsv}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-[--line-2] bg-[--bg-3] px-3 text-xs font-medium text-[--txt-1] hover:bg-[--bg-2]"
        >
          <Download className="h-3.5 w-3.5" />
          Экспорт CSV
        </button>

        <span className="ml-auto text-xs text-[--txt-3]">
          {filtered.length} из {entries.length}
        </span>
      </div>

      {showCategories && (
        <div className="flex shrink-0 flex-wrap gap-1.5 border-b border-[--line-1] bg-[--bg-1] px-4 py-2">
          {CATEGORIES.map((c) => {
            const count = categoryCounts[c.key] ?? 0
            return (
              <button
                key={c.key}
                type="button"
                onClick={() => setCategory(c.key)}
                className={cn(
                  'rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors',
                  category === c.key
                    ? 'bg-[--blue] text-white'
                    : 'bg-[--bg-3] text-[--txt-2] hover:text-[--txt-1]',
                  count === 0 && category !== c.key && 'opacity-40',
                )}
              >
                {c.label}
                {c.key !== 'all' && (
                  <span className="ml-1 opacity-70">{count}</span>
                )}
              </button>
            )
          })}
        </div>
      )}

      <div className="relative flex-1">
        {filtered.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[--txt-3]">
            Нет записей
          </div>
        ) : (
          <FixedSizeList
            ref={listRef}
            height={typeof window !== 'undefined' ? window.innerHeight - (showCategories ? 220 : 180) : 600}
            width="100%"
            itemCount={filtered.length}
            itemSize={ROW_HEIGHT}
          >
            {Row}
          </FixedSizeList>
        )}
      </div>

      {expandedEntries.length > 0 && (
        <div className="max-h-48 shrink-0 overflow-auto border-t border-[--line-1] bg-[--bg-1] p-3 font-mono text-[11px]">
          {expandedEntries.map((e) => (
            <div key={e.id} className="mb-2 border-l-2 border-[--blue] pl-3">
              <div className="text-[--txt-3]">
                {formatTime(e.created_at)} · {e.action_type}
              </div>
              <pre className="mt-1 whitespace-pre-wrap text-[--txt-1]">
                {JSON.stringify(e.details ?? {}, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )
}
