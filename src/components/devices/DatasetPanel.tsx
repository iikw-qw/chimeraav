import { useEffect, useMemo, useState, type DragEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, Search, Database } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { Input } from '../ui'
import { cn } from '../../lib/cn'

export interface Dataset {
  id: string
  name: string
  item_count?: number
  preview_url?: string | null
  linked_device_ids?: string[]
}

async function fetchDatasets(): Promise<Dataset[]> {
  try {
    const { data } = await api.get<Dataset[]>('/api/datasets', {
      params: { limit: 500 },
    })
    return data
  } catch {
    return []
  }
}

interface DragState {
  datasetId: string
  startX: number
  startY: number
  curX: number
  curY: number
}

export interface DatasetPanelProps {
  open: boolean
  onClose: () => void
  onDropOnDevice?: (datasetId: string, deviceId: string) => void
}

export function DatasetPanel({ open, onClose, onDropOnDevice }: DatasetPanelProps) {
  const [q, setQ] = useState('')
  const [drag, setDrag] = useState<DragState | null>(null)

  const { data: datasets = [] } = useQuery({
    queryKey: ['datasets'],
    queryFn: fetchDatasets,
    enabled: open,
    refetchInterval: 10_000,
  })

  const filtered = useMemo(
    () =>
      q
        ? datasets.filter((d) => d.name.toLowerCase().includes(q.toLowerCase()))
        : datasets,
    [datasets, q],
  )

  useEffect(() => {
    if (!drag) return
    const onMove = (e: MouseEvent) => {
      setDrag((s) => (s ? { ...s, curX: e.clientX, curY: e.clientY } : s))
    }
    const onUp = (e: MouseEvent) => {
      const target = document.elementFromPoint(e.clientX, e.clientY)
      const cell = target?.closest('[data-device-id]')
      const deviceId = cell?.getAttribute('data-device-id')
      if (deviceId && drag) onDropOnDevice?.(drag.datasetId, deviceId)
      setDrag(null)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [drag, onDropOnDevice])

  const handleDragStart = (e: DragEvent<HTMLDivElement>) => {
    // prevent native ghost — we use our own SVG overlay
    e.preventDefault()
  }

  const bezierPath = useMemo(() => {
    if (!drag) return ''
    const { startX, startY, curX, curY } = drag
    const dx = curX - startX
    const c1x = startX + dx * 0.5
    const c1y = startY
    const c2x = curX - dx * 0.5
    const c2y = curY
    return `M ${startX} ${startY} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${curX} ${curY}`
  }, [drag])

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.aside
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 320, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 260, damping: 28 }}
            className="absolute inset-y-0 right-0 z-40 flex w-80 flex-col border-l border-[--line-1] bg-[--bg-1] shadow-2xl"
          >
            <div className="flex h-12 items-center justify-between border-b border-[--line-1] px-4">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-[--blue]" />
                <span className="text-sm font-medium text-[--txt-1]">
                  Датасеты
                </span>
              </div>
              <button
                onClick={onClose}
                className="rounded-md p-1 text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-3">
              <Input
                placeholder="Поиск датасета..."
                value={q}
                onChange={(e) => setQ(e.target.value)}
                leftIcon={<Search className="h-3.5 w-3.5" />}
                className="h-9 text-xs"
              />
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto px-3 pb-3">
              {filtered.length === 0 && (
                <div className="mt-6 text-center text-xs text-[--txt-3]">
                  {q ? 'Ничего не найдено' : 'Нет датасетов'}
                </div>
              )}
              {filtered.map((ds) => (
                <div
                  key={ds.id}
                  onDragStart={handleDragStart}
                  onMouseDown={(e) => {
                    setDrag({
                      datasetId: ds.id,
                      startX: e.clientX,
                      startY: e.clientY,
                      curX: e.clientX,
                      curY: e.clientY,
                    })
                  }}
                  className={cn(
                    'flex cursor-grab items-center gap-3 rounded-lg border border-[--line-1] bg-[--bg-2] p-2 transition-colors',
                    'hover:border-[--line-3] hover:bg-[--bg-3]',
                    drag?.datasetId === ds.id && 'cursor-grabbing opacity-60',
                  )}
                >
                  <div className="h-10 w-10 shrink-0 overflow-hidden rounded-md bg-[--bg-3]">
                    {ds.preview_url ? (
                      <img
                        src={ds.preview_url}
                        alt={ds.name}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-[--txt-3]">
                        <Database className="h-4 w-4" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium text-[--txt-1]">
                      {ds.name}
                    </div>
                    <div className="text-[10px] text-[--txt-2]">
                      {ds.item_count ?? 0} элементов
                      {ds.linked_device_ids?.length
                        ? ` · ${ds.linked_device_ids.length} привязок`
                        : ''}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {drag && (
        <svg className="pointer-events-none fixed inset-0 z-50 h-full w-full">
          <path
            d={bezierPath}
            stroke="#5B9BFF"
            strokeWidth={2}
            strokeDasharray="8 4"
            fill="none"
          >
            <animate
              attributeName="stroke-dashoffset"
              from="0"
              to="-24"
              dur="0.6s"
              repeatCount="indefinite"
            />
          </path>
        </svg>
      )}
    </>
  )
}
