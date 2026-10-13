// DeviceMap — page that aggregates live H.264 streams from every active
// device. Pulls the active-stream registry from the FastAPI sidecar and
// hands the list to <DeviceGrid />.
//
// We deliberately drive the page off `/api/streams` (not `/api/devices`):
// the device table contains *registered* devices, but a stream is only live
// while the Android agent is connected to /api/ws/stream/{id}. So this page
// only shows devices that are actually streaming right now.

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Layers, Play, Square } from 'lucide-react'
import { api } from '../../api/client'
import { Button } from '../../components/ui'
import { DeviceGrid, type DeviceGridItem } from '../../components/streaming/DeviceGrid'
import { useDevices, startStreamingAll, stopStreamingAll } from '../../hooks/useDevices'
import { toast } from '../../hooks/useToast'

interface StreamSummary {
  device_id: string
  fps: number
  bitrate_bps: number
  resolution: string | null
  viewers: number
  has_keyframe: boolean
  started_at: number
  metadata: Record<string, unknown> | null
}

const COLUMN_OPTIONS = [3, 4, 5] as const

async function fetchStreams(): Promise<StreamSummary[]> {
  const { data } = await api.get<StreamSummary[]>('/api/streams')
  return data
}

export default function DeviceMap() {
  const [columns, setColumns] = useState<(typeof COLUMN_OPTIONS)[number]>(3)
  const [startingAll, setStartingAll] = useState(false)
  const [stoppingAll, setStoppingAll] = useState(false)

  const handleStartAll = async () => {
    setStartingAll(true)
    try {
      const data = await startStreamingAll()
      const ok = data.results.filter((r) => r.status === 'ok').length
      const fail = data.results.filter((r) => r.status === 'error').length
      if (fail === 0) {
        toast.success(`Стриминг запущен на ${ok} устройствах`)
      } else {
        toast.warning(`Запущено: ${ok}, ошибок: ${fail}`)
      }
    } catch (err) {
      toast.danger((err as Error).message, 'Запуск стриминга')
    } finally {
      setStartingAll(false)
    }
  }

  const handleStopAll = async () => {
    setStoppingAll(true)
    try {
      await stopStreamingAll()
      toast.success('Стриминг остановлен')
    } catch (err) {
      toast.danger((err as Error).message, 'Остановка стриминга')
    } finally {
      setStoppingAll(false)
    }
  }
  const { data: streams } = useQuery({
    queryKey: ['streams'],
    queryFn: fetchStreams,
    refetchInterval: 5_000,
    staleTime: 2_000,
  })
  const { data: devices } = useDevices()

  const items = useMemo<DeviceGridItem[]>(() => {
    const list = streams ?? []
    return list.map((s) => {
      const dev = devices?.find((d) => d.id === s.device_id)
      const title =
        dev?.name ?? (s.metadata?.['model'] as string | undefined) ?? s.device_id
      return { id: s.device_id, title }
    })
  }, [streams, devices])

  const totalBitrate = (streams ?? []).reduce((a, s) => a + s.bitrate_bps, 0)
  const totalFps = (streams ?? []).reduce((a, s) => a + s.fps, 0)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="h-full overflow-y-auto p-5 space-y-4"
    >
      <header className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-[--text-1] text-lg font-semibold">
            <Layers size={18} />
            Карта устройств
          </div>
          <div className="text-xs text-[--text-3]">
            Активных стримов: {items.length} ·{' '}
            {(totalBitrate / 1_000_000).toFixed(1)} Mbps ·{' '}
            {totalFps.toFixed(0)} fps суммарно
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <Button
            size="sm"
            variant="primary"
            leftIcon={<Play className="h-3.5 w-3.5" />}
            onClick={handleStartAll}
            disabled={startingAll}
          >
            {startingAll ? 'Запуск...' : 'Стриминг на все'}
          </Button>
          {items.length > 0 && (
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<Square className="h-3.5 w-3.5" />}
              onClick={handleStopAll}
              disabled={stoppingAll}
            >
              {stoppingAll ? 'Стоп...' : 'Стоп'}
            </Button>
          )}
          <span className="text-[--text-3]">Сетка:</span>
          {COLUMN_OPTIONS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setColumns(c)}
              className={
                'rounded-md border px-2 py-1 ' +
                (columns === c
                  ? 'border-[--line-3] bg-[--bg-3] text-[--text-1]'
                  : 'border-[--line-1] bg-[--bg-2] text-[--text-3] hover:text-[--text-1]')
              }
            >
              {c}×{c}
            </button>
          ))}
        </div>
      </header>
      <DeviceGrid devices={items} columns={columns} />
    </motion.div>
  )
}
