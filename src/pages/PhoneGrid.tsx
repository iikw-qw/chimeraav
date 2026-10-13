import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Camera,
  Grid2x2,
  Grid3x3,
  LayoutGrid,
  Link2,
  MessageSquare,
  Package,
  Play,
  Search,
  Smartphone,
  Wrench,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Input, Switch } from '../components/ui'
import { cn } from '../lib/cn'
import { useAppStore, CELL_SIZE_PX, type CellSize } from '../stores/appStore'
import {
  DEVICES_QUERY_KEY,
  disconnectDevice,
  pauseDevice,
  rebootDevice,
  screenshotUrl,
  useDevices,
  type Device,
} from '../hooks/useDevices'
import { DeviceCell } from '../components/devices/DeviceCell'
import { DatasetPanel } from '../components/devices/DatasetPanel'
import { DeviceViewer } from '../components/devices/DeviceViewer'
import {
  ConnectionCanvas,
  type Connection,
} from '../components/devices/ConnectionCanvas'
import { CountUp } from '../components/devices/CountUp'
import { toast } from '../hooks/useToast'
import { useTasks } from '../hooks/useTasks'
import { useUnreadCount } from '../hooks/useIncomingMessages'
import { useAccounts } from '../hooks/useAccounts'
import {
  DATASETS_QUERY_KEY,
  linkDataset,
  useDatasets,
  type DatasetRow,
} from '../hooks/useDatasets'
import { Modal } from '../components/ui'
import { FixEverythingWizard } from '../components/FixEverythingWizard'
import DeviceSetupGuide from '../components/DeviceSetupGuide'

const SIZE_OPTIONS: { value: CellSize; icon: typeof LayoutGrid }[] = [
  { value: 'lg', icon: Grid2x2 },
  { value: 'md', icon: LayoutGrid },
  { value: 'sm', icon: Grid3x3 },
]

export function PhoneGrid() {
  const {
    cellSize,
    setCellSize,
    syncMouse,
    setSyncMouse,
    syncKeys,
    setSyncKeys,
    selectedGroup,
    setSelectedGroup,
    datasetPanelOpen,
    toggleDatasetPanel,
    setDatasetPanelOpen,
  } = useAppStore()

  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [platformFilter, setPlatformFilter] = useState<'all' | 'android' | 'ios'>('all')
  const [connections, setConnections] = useState<Connection[]>([])
  const gridRef = useRef<HTMLDivElement>(null)

  const { data: devices = [], isLoading } = useDevices()
  const { data: datasets = [] } = useDatasets()
  const { data: tasks = [] } = useTasks()
  const { data: accounts = [] } = useAccounts()
  const { data: unreadCount = 0 } = useUnreadCount()

  const pendingCount = useMemo(
    () => tasks.filter((t) => t.status === 'pending').length,
    [tasks],
  )
  const warmingRatio = useMemo(() => {
    if (!accounts.length) return 0
    const warming = accounts.filter((a) => a.status === 'warming').length
    return warming / accounts.length
  }, [accounts])

  const [viewerDevice, setViewerDevice] = useState<Device | null>(null)
  const [linkFor, setLinkFor] = useState<Device | null>(null)
  const [fixSerial, setFixSerial] = useState<string | null>(null)

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:17842/api/ws/devices')
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as { event: string; serial: string }
        if (data.event === 'device_connected') {
          toast.success(`Device connected: ${data.serial}`)
          qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
        }
        if (data.event === 'device_disconnected') {
          toast.warning(`Device disconnected: ${data.serial}`)
          qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
        }
      } catch {}
    }
    return () => ws.close()
  }, [qc])

  const groups = useMemo(() => {
    const s = new Set<string>()
    for (const d of devices) if (d.group_name) s.add(d.group_name)
    return Array.from(s).sort()
  }, [devices])

  const filtered = useMemo<Device[]>(() => {
    const needle = search.trim().toLowerCase()
    return devices.filter((d) => {
      if (platformFilter !== 'all' && d.platform !== platformFilter) return false
      if (selectedGroup !== 'all' && d.group_name !== selectedGroup) return false
      if (!needle) return true
      return (
        d.name.toLowerCase().includes(needle) ||
        (d.phone_number ?? '').toLowerCase().includes(needle) ||
        (d.serial ?? '').toLowerCase().includes(needle)
      )
    })
  }, [devices, search, selectedGroup, platformFilter])

  const platformCounts = useMemo(() => {
    let android = 0
    let ios = 0
    for (const d of devices) {
      if (d.platform === 'android') android++
      else if (d.platform === 'ios') ios++
    }
    return { android, ios, all: devices.length }
  }, [devices])

  const onlineCount = useMemo(
    () => devices.filter((d) => d.status === 'online').length,
    [devices],
  )

  const handleDropDataset = (datasetId: string, deviceId: string) => {
    const id = `${datasetId}:${deviceId}`
    setConnections((prev) =>
      prev.some((c) => c.id === id) ? prev : [...prev, { id, datasetId, deviceId }],
    )
    // persist link server-side
    void linkDataset(datasetId, deviceId)
      .then(() => {
        toast.success('Датасет привязан')
        qc.invalidateQueries({ queryKey: DATASETS_QUERY_KEY })
      })
      .catch((err) => toast.danger((err as Error).message))
  }

  const handleRemoveConnection = (c: Connection) => {
    setConnections((prev) => prev.filter((x) => x.id !== c.id))
  }

  const cellPx = CELL_SIZE_PX[cellSize]

  // ───────── Context-menu handlers ─────────
  const onOpenFullscreen = useCallback((d: Device) => setViewerDevice(d), [])

  const onScreenshot = useCallback(async (d: Device) => {
    try {
      const res = await fetch(screenshotUrl(d.id) + `?t=${Date.now()}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${d.name}-${Date.now()}.png`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      toast.success('Скриншот сохранён')
    } catch (err) {
      toast.danger(`Не удалось снять скриншот: ${(err as Error).message}`)
    }
  }, [])

  const onReboot = useCallback(async (d: Device) => {
    if (!confirm(`Перезагрузить устройство «${d.name}»?`)) return
    try {
      await rebootDevice(d.id)
      toast.success('Перезагрузка отправлена')
      qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }, [qc])

  const onDisconnect = useCallback(async (d: Device) => {
    try {
      await disconnectDevice(d.id)
      toast.success('Устройство отключено')
      qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }, [qc])

  const onPauseToggle = useCallback(async (d: Device) => {
    const newPaused = d.status !== 'paused'
    try {
      await pauseDevice(d.id, newPaused)
      toast.success(newPaused ? 'Устройство на паузе' : 'Устройство возобновлено')
      qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }, [qc])

  const onInfo = useCallback((d: Device) => setViewerDevice(d), [])
  const onOpenProfile = useCallback((d: Device) => setViewerDevice(d), [])
  const onLinkDataset = useCallback((d: Device) => setLinkFor(d), [])

  const onScreenshotAll = useCallback(async () => {
    if (filtered.length === 0) return
    let ok = 0
    await Promise.all(
      filtered.map(async (d) => {
        try {
          await onScreenshot(d)
          ok++
        } catch {
          // counted by toast
        }
      }),
    )
    toast.info(`Скриншотов сохранено: ${ok}/${filtered.length}`)
  }, [filtered, onScreenshot])

  const onInstallApk = useCallback(() => {
    toast.info('Установка APK — скоро. Выберите файл в меню устройства.')
  }, [])

  const onInstallAgent = useCallback(async () => {
    try {
      const { data } = await (await import('../api/client')).api.post('/api/v1/devices/install-agent')
      if (data.installed > 0) {
        toast.success(`Agent installed on ${data.installed} device(s)`)
      } else {
        toast.info(`No devices to install (${data.total} found, ${data.failed} failed)`)
      }
    } catch {
      toast.danger('Failed to install agent')
    }
  }, [])

  const onStartStreamAll = useCallback(async () => {
    try {
      const { data } = await (await import('../api/client')).api.post('/api/v1/stream/start-all')
      const ok = data.results?.filter((r: { streaming: boolean }) => r.streaming).length ?? 0
      toast.success(`Streaming started on ${ok}/${data.total} device(s)`)
    } catch {
      toast.danger('Failed to start streaming')
    }
  }, [])

  const onScanDmsAll = useCallback(async () => {
    try {
      const { data } = await (await import('../api/client')).api.post('/api/v1/dm/scan', { serial: '', platform: 'instagram' })
      const male = data?.male?.length ?? 0
      const female = data?.female?.length ?? 0
      toast.success(`DM scan complete: ${male} male, ${female} female`)
    } catch {
      toast.danger('Failed to scan DMs')
    }
  }, [])

  return (
    <div className="relative flex h-full w-full flex-col bg-[--bg-0]">
      <div className="no-drag flex h-12 items-center gap-3 border-b border-[--line-1] bg-[--bg-1] px-4">
        <div className="flex items-center gap-2 text-xs text-[--txt-2]">
          <span>Sync Mouse</span>
          <Switch checked={syncMouse} onChange={setSyncMouse} />
        </div>
        <div className="flex items-center gap-2 text-xs text-[--txt-2]">
          <span>Sync Keys</span>
          <Switch checked={syncKeys} onChange={setSyncKeys} />
        </div>

        <div className="h-6 w-px bg-[--line-2]" />

        <select
          value={selectedGroup}
          onChange={(e) => setSelectedGroup(e.target.value)}
          className="h-8 rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none focus:border-[--blue]"
        >
          <option value="all">Все группы</option>
          {groups.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-0.5 rounded-lg border border-[--line-2] bg-[--bg-3] p-0.5">
          {SIZE_OPTIONS.map(({ value, icon: Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setCellSize(value)}
              className={cn(
                'flex h-7 w-7 items-center justify-center rounded-md transition-colors',
                cellSize === value
                  ? 'bg-[--blue] text-white'
                  : 'text-[--txt-2] hover:bg-[--bg-2] hover:text-[--txt-1]',
              )}
            >
              <Icon className="h-3.5 w-3.5" />
            </button>
          ))}
        </div>

        <div className="h-6 w-px bg-[--line-2]" />

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Camera className="h-3.5 w-3.5" />}
          onClick={onScreenshotAll}
          disabled={filtered.length === 0}
        >
          Скриншот всех
        </Button>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Package className="h-3.5 w-3.5" />}
          onClick={onInstallApk}
        >
          Установить APK
        </Button>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Smartphone className="h-3.5 w-3.5" />}
          onClick={onInstallAgent}
        >
          Install Agent
        </Button>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Play className="h-3.5 w-3.5" />}
          onClick={onStartStreamAll}
          disabled={filtered.length === 0}
        >
          Stream All
        </Button>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<MessageSquare className="h-3.5 w-3.5" />}
          onClick={onScanDmsAll}
        >
          Scan DMs
        </Button>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Wrench className="h-3.5 w-3.5" />}
          onClick={() => {
            const first = filtered.find((d) => d.status === 'online')
            if (first) setFixSerial(first.id)
            else toast.warning('No online device to fix')
          }}
        >
          Fix Everything
        </Button>
        <Button
          variant={datasetPanelOpen ? 'primary' : 'secondary'}
          size="sm"
          leftIcon={<Link2 className="h-3.5 w-3.5" />}
          onClick={toggleDatasetPanel}
        >
          Связать датасет
        </Button>

        <div className="ml-auto w-64">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск устройств..."
            leftIcon={<Search className="h-3.5 w-3.5" />}
            className="h-8 text-xs"
          />
        </div>
      </div>

      <div className="flex h-9 items-center gap-1 border-b border-[--line-1] bg-[--bg-1] px-4 text-xs">
        {(
          [
            { k: 'all', l: 'Все', n: platformCounts.all },
            { k: 'android', l: 'Android', n: platformCounts.android },
            { k: 'ios', l: 'Apple iOS', n: platformCounts.ios },
          ] as const
        ).map((t) => (
          <button
            key={t.k}
            type="button"
            onClick={() => setPlatformFilter(t.k)}
            className={cn(
              'flex h-7 items-center gap-1.5 rounded-md px-3 transition-colors',
              platformFilter === t.k
                ? 'bg-[--blue]/15 text-[--blue]'
                : 'text-[--txt-2] hover:bg-[--bg-2] hover:text-[--txt-1]',
            )}
          >
            <span className="font-medium">{t.l}</span>
            <span className="rounded bg-[--bg-3] px-1 text-[10px] tabular-nums text-[--txt-3]">
              {t.n}
            </span>
          </button>
        ))}
      </div>

      <div ref={gridRef} className="relative flex-1 overflow-auto p-4">
        <motion.div
          className="grid gap-3"
          style={{
            gridTemplateColumns: `repeat(auto-fill, minmax(${cellPx}px, 1fr))`,
          }}
          initial="hidden"
          animate="show"
        >
          {isLoading && devices.length === 0 ? (
            <div className="col-span-full py-12 text-center text-sm text-[--txt-3]">
              Загрузка устройств...
            </div>
          ) : devices.length === 0 ? (
            <div className="col-span-full py-6">
              <DeviceSetupGuide
                deviceConnected={false}
                agentInstalled={false}
                platformsDetected={[]}
                onCheckConnection={async () => {
                  try {
                    const { api: apiClient } = await import('../api/client')
                    const res = await apiClient.get('/api/devices')
                    const data = res.data as any[]
                    if (data.length > 0) {
                      qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
                      toast.success('Device found!')
                    } else {
                      toast.danger('No devices found. Check USB connection.')
                    }
                  } catch {
                    toast.danger('Failed to check connection')
                  }
                }}
                onInstallAgent={onInstallAgent}
                onDetectPlatforms={() => toast.info('Connect a device first')}
                onDismiss={() => {}}
              />
            </div>
          ) : filtered.length === 0 ? (
            <div className="col-span-full py-12 text-center text-sm text-[--txt-3]">
              Нет устройств по фильтру
            </div>
          ) : (
            filtered.map((d, i) => (
              <DeviceCell
                key={d.id}
                device={d}
                index={i}
                onOpenFullscreen={onOpenFullscreen}
                onScreenshot={onScreenshot}
                onOpenProfile={onOpenProfile}
                onLinkDataset={onLinkDataset}
                onReboot={onReboot}
                onInfo={onInfo}
                onPauseToggle={onPauseToggle}
                onDisconnect={onDisconnect}
              />
            ))
          )}
        </motion.div>

        <ConnectionCanvas
          connections={connections}
          containerRef={gridRef}
          onRemove={handleRemoveConnection}
        />
      </div>

      <div className="flex h-8 items-center gap-6 border-t border-[--line-1] bg-[--bg-1] px-4 text-xs text-[--txt-2]">
        <span>
          📱 <CountUp value={onlineCount} />/<CountUp value={devices.length} /> online
        </span>
        <span>
          📋 Queue: <CountUp value={pendingCount} />
        </span>
        <span>
          🔥 Warmup: <CountUp value={warmingRatio} format={(n) => n.toFixed(2)} />
        </span>
        <span>
          💬 <CountUp value={unreadCount} /> new
        </span>
      </div>

      <DatasetPanel
        open={datasetPanelOpen}
        onClose={() => setDatasetPanelOpen(false)}
        onDropOnDevice={handleDropDataset}
      />

      <DeviceViewer device={viewerDevice} onClose={() => setViewerDevice(null)} />

      <LinkDatasetModal
        device={linkFor}
        datasets={datasets}
        onClose={() => setLinkFor(null)}
        onLinked={() => {
          setLinkFor(null)
          qc.invalidateQueries({ queryKey: DATASETS_QUERY_KEY })
        }}
      />

      {fixSerial && (
        <FixEverythingWizard
          serial={fixSerial}
          onComplete={() => qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })}
          onClose={() => setFixSerial(null)}
        />
      )}
    </div>
  )
}

function LinkDatasetModal({
  device,
  datasets,
  onClose,
  onLinked,
}: {
  device: Device | null
  datasets: DatasetRow[]
  onClose: () => void
  onLinked: () => void
}) {
  const [datasetId, setDatasetId] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!device || !datasetId) return
    setBusy(true)
    try {
      await linkDataset(datasetId, device.id)
      toast.success('Датасет привязан')
      onLinked()
      setDatasetId('')
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={device !== null}
      onClose={onClose}
      title={device ? `Привязать датасет к ${device.name}` : ''}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Отмена
          </Button>
          <Button variant="primary" onClick={submit} disabled={!datasetId || busy}>
            Привязать
          </Button>
        </>
      }
    >
      <label className="mb-1 block text-xs text-[--txt-2]">Датасет</label>
      <select
        value={datasetId}
        onChange={(e) => setDatasetId(e.target.value)}
        className="w-full rounded-md border border-[--line-2] bg-[--bg-1] px-3 py-2 text-sm text-[--txt-1] focus:outline-none focus:ring-2 focus:ring-[--blue]"
      >
        <option value="">— выберите датасет —</option>
        {datasets.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name} ({d.photo_count} фото)
          </option>
        ))}
      </select>
    </Modal>
  )
}
