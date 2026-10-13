import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ChevronLeft,
  ChevronRight,
  Eraser,
  FolderOpen,
  Grid3x3,
  Image as ImageIcon,
  Link2,
  Link2Off,
  RefreshCw,
  Trash2,
  Upload,
  Video,
  X,
  ZoomIn,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Badge, Button, ContextMenu, Input, Modal, ProgressBar } from '../components/ui'
import type { ContextMenuItem } from '../components/ui'
import { cn } from '../lib/cn'
import { toast } from '../hooks/useToast'
import { useDevices, type Device } from '../hooks/useDevices'
import {
  DATASETS_QUERY_KEY,
  cleanDatasetMetadata,
  datasetFileUrl,
  deleteDataset,
  getDataset,
  linkDataset,
  unlinkDataset,
  uploadDataset,
  useDatasetFiles,
  useDatasets,
  type DatasetRow,
} from '../hooks/useDatasets'

type KindFilter = 'all' | 'photo' | 'video'

export function Datasets() {
  const { data: datasets = [], isLoading } = useDatasets()
  const { data: devices = [] } = useDevices()
  const qc = useQueryClient()

  const [kindFilter, setKindFilter] = useState<KindFilter>('all')
  const [menu, setMenu] = useState<{ x: number; y: number; dataset: DatasetRow } | null>(null)
  const [wearMapFor, setWearMapFor] = useState<DatasetRow | null>(null)
  const [linkFor, setLinkFor] = useState<DatasetRow | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [viewer, setViewer] = useState<DatasetRow | null>(null)

  const filteredDatasets = useMemo(() => {
    if (kindFilter === 'all') return datasets
    if (kindFilter === 'video') return datasets.filter((d) => d.video_count > 0)
    return datasets.filter((d) => d.photo_count > 0)
  }, [datasets, kindFilter])

  const deviceName = (id: string | null | undefined) =>
    id ? devices.find((d) => d.id === id)?.name ?? id.slice(0, 8) : null

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: DATASETS_QUERY_KEY })
    qc.invalidateQueries({ queryKey: ['dataset-files'] })
  }

  const handleDelete = async (ds: DatasetRow) => {
    try {
      await deleteDataset(ds.id)
      toast.success('Датасет удалён')
      invalidate()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const handleClean = async (ds: DatasetRow) => {
    try {
      await cleanDatasetMetadata(ds.id)
      toast.success('Очистка метаданных запущена')
      invalidate()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const handleUnlink = async (ds: DatasetRow) => {
    try {
      await unlinkDataset(ds.id)
      toast.success('Привязка снята')
      invalidate()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const openWearMap = async (ds: DatasetRow) => {
    try {
      const fresh = await getDataset(ds.id)
      setWearMapFor(fresh)
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const menuItems: ContextMenuItem[] = useMemo(() => {
    if (!menu) return []
    const ds = menu.dataset
    return [
      {
        label: 'Wear Map',
        icon: <Grid3x3 className="h-3.5 w-3.5" />,
        onSelect: () => openWearMap(ds),
      },
      ds.linked_device_id
        ? {
            label: 'Отвязать',
            icon: <Link2Off className="h-3.5 w-3.5" />,
            onSelect: () => handleUnlink(ds),
          }
        : {
            label: 'Связать',
            icon: <Link2 className="h-3.5 w-3.5" />,
            onSelect: () => setLinkFor(ds),
          },
      {
        label: 'Очистить мета',
        icon: <Eraser className="h-3.5 w-3.5" />,
        onSelect: () => handleClean(ds),
        disabled: ds.metadata_cleaned,
      },
      { separator: true, label: '' },
      {
        label: 'Удалить',
        icon: <Trash2 className="h-3.5 w-3.5" />,
        onSelect: () => handleDelete(ds),
        danger: true,
      },
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menu])

  return (
    <motion.div
      className="h-full overflow-auto bg-[--bg-0] p-6"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[--txt-1]">Датасеты</h1>
          <p className="text-sm text-[--txt-3]">
            {filteredDatasets.length} из {datasets.length}{' '}
            {datasets.length === 1 ? 'набор' : 'наборов'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            leftIcon={<RefreshCw className="h-4 w-4" />}
            onClick={async () => {
              try {
                const { api: apiClient } = await import('../api/client')
                await apiClient.post('/api/v1/datasets/sync-to-device', { dataset_id: 'all', serial: 'all' })
                toast.success('Sync started for all devices')
              } catch { toast.danger('Sync failed') }
            }}
          >
            Sync All
          </Button>
          <Button
            variant="primary"
            leftIcon={<Upload className="h-4 w-4" />}
            onClick={() => setUploadOpen(true)}
          >
            Загрузить
          </Button>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-1 rounded-lg border border-[--line-1] bg-[--bg-1] p-1">
        {([
          { key: 'all', label: 'Все' },
          { key: 'photo', label: 'Фото' },
          { key: 'video', label: 'Видео' },
        ] as { key: KindFilter; label: string }[]).map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setKindFilter(t.key)}
            className={cn(
              'rounded-md px-3 py-1 text-xs transition-colors',
              kindFilter === t.key
                ? 'bg-[--blue]/15 text-[--blue]'
                : 'text-[--txt-2] hover:text-[--txt-1]',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <UploadZone onOpen={() => setUploadOpen(true)} />

      {isLoading ? (
        <div className="py-16 text-center text-sm text-[--txt-3]">Загрузка…</div>
      ) : filteredDatasets.length === 0 ? (
        <div className="py-16 text-center text-sm text-[--txt-3]">
          {datasets.length === 0
            ? 'Нет датасетов. Загрузите первый, чтобы начать.'
            : 'По фильтру ничего не найдено.'}
        </div>
      ) : (
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredDatasets.map((ds) => (
            <DatasetCard
              key={ds.id}
              dataset={ds}
              deviceName={deviceName(ds.linked_device_id)}
              onContextMenu={(e) => {
                e.preventDefault()
                setMenu({ x: e.clientX, y: e.clientY, dataset: ds })
              }}
              onOpenViewer={() => setViewer(ds)}
            />
          ))}
        </div>
      )}

      <ContextMenu
        open={menu !== null}
        x={menu?.x ?? 0}
        y={menu?.y ?? 0}
        items={menuItems}
        onClose={() => setMenu(null)}
      />

      <WearMapModal dataset={wearMapFor} onClose={() => setWearMapFor(null)} />

      <DatasetViewerModal dataset={viewer} onClose={() => setViewer(null)} />

      <LinkModal
        dataset={linkFor}
        devices={devices}
        onClose={() => setLinkFor(null)}
        onLinked={() => {
          setLinkFor(null)
          invalidate()
        }}
      />

      <UploadModal
        open={uploadOpen}
        devices={devices}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => {
          setUploadOpen(false)
          invalidate()
        }}
      />
    </motion.div>
  )
}

function DatasetCard({
  dataset,
  deviceName,
  onContextMenu,
  onOpenViewer,
}: {
  dataset: DatasetRow
  deviceName: string | null
  onContextMenu: (e: React.MouseEvent) => void
  onOpenViewer: () => void
}) {
  const wearValues = Object.values(dataset.wear_map ?? {})
  const maxWear = wearValues.length ? Math.max(...wearValues, 1) : 1
  const avgWear = wearValues.length
    ? wearValues.reduce((a, b) => a + b, 0) / wearValues.length
    : 0
  const wearPct = Math.min(100, (avgWear / maxWear) * 100)

  const { data: files } = useDatasetFiles(dataset.id)
  const isVideoOnly = dataset.video_count > 0 && dataset.photo_count === 0
  const previews = (files?.photos ?? []).slice(0, 4)
  const videoPreviews = (files?.videos ?? []).slice(0, 4)

  return (
    <motion.div
      layout
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.15 }}
      onContextMenu={onContextMenu}
      onClick={onOpenViewer}
      className="group cursor-pointer overflow-hidden rounded-xl border border-[--line-1] bg-[--bg-1] shadow-sm"
    >
      <div className="grid aspect-square grid-cols-2 grid-rows-2 gap-1 bg-[--bg-2] p-1">
        {Array.from({ length: 4 }).map((_, i) => {
          const p = previews[i]
          const v = videoPreviews[i]
          if (p) {
            return (
              <PreviewImage
                key={p.name}
                src={datasetFileUrl(dataset.id, p.name)}
                alt={p.name}
              />
            )
          }
          if (isVideoOnly && v) {
            return (
              <div
                key={v.name}
                className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-lg bg-[--bg-3]"
              >
                <Video className="h-6 w-6 text-[--txt-2]" />
                <span className="absolute bottom-0 left-0 right-0 truncate bg-black/60 px-1 text-[9px] text-white">
                  {v.name}
                </span>
              </div>
            )
          }
          return (
            <div
              key={`empty-${i}`}
              className="flex items-center justify-center rounded-lg bg-[--bg-3] text-[--txt-3]"
            >
              {isVideoOnly ? (
                <Video className="h-6 w-6 opacity-40" />
              ) : (
                <ImageIcon className="h-6 w-6 opacity-40" />
              )}
            </div>
          )
        })}
      </div>

      <div className="space-y-3 p-4">
        <div>
          <div className="truncate text-sm font-medium text-[--txt-1]">{dataset.name}</div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-[--txt-3]">
            <span className="inline-flex items-center gap-1">
              <ImageIcon className="h-3 w-3" />
              {dataset.photo_count} фото
            </span>
            <span>·</span>
            <span className="inline-flex items-center gap-1">
              <Video className="h-3 w-3" />
              {dataset.video_count} видео
            </span>
          </div>
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between text-[10px] text-[--txt-3]">
            <span>SIPR износ</span>
            <span>{Math.round(wearPct)}%</span>
          </div>
          <ProgressBar value={wearPct} />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant={deviceName ? 'info' : 'neutral'}>
            {deviceName ? `📱 ${deviceName}` : 'Не привязан'}
          </Badge>
          <Badge variant={dataset.metadata_cleaned ? 'success' : 'warning'}>
            {dataset.metadata_cleaned ? 'Мета очищена' : 'Мета не очищена'}
          </Badge>
          {isVideoOnly && <Badge variant="info">🎥 Видео-датасет</Badge>}
          {dataset.photo_count > 0 && dataset.video_count > 0 && (
            <Badge variant="neutral">Микс</Badge>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function UploadZone({ onOpen }: { onOpen: () => void }) {
  const [hover, setHover] = useState(false)
  return (
    <div
      onClick={onOpen}
      onDragOver={(e) => {
        e.preventDefault()
        setHover(true)
      }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault()
        setHover(false)
        onOpen()
      }}
      className={cn(
        'flex h-40 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed transition-colors',
        hover
          ? 'border-[--blue] bg-[--blue]/10'
          : 'border-[--line-2] hover:border-[--blue] hover:bg-[--blue]/5',
      )}
    >
      <Upload className="mb-2 h-6 w-6 text-[--txt-2]" />
      <div className="text-sm font-medium text-[--txt-1]">Перетащите файлы сюда</div>
      <div className="text-xs text-[--txt-3]">или кликните, чтобы выбрать</div>
    </div>
  )
}

function DatasetViewerModal({
  dataset,
  onClose,
}: {
  dataset: DatasetRow | null
  onClose: () => void
}) {
  const { data, isLoading } = useDatasetFiles(dataset?.id)
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  const photoUrls = useMemo(() => {
    if (!dataset || !data) return [] as { url: string; name: string }[]
    return data.photos.map((p) => ({
      url: datasetFileUrl(dataset.id, p.name),
      name: p.name,
    }))
  }, [dataset, data])

  return (
    <>
      <Modal
        open={dataset !== null}
        onClose={onClose}
        title={dataset ? dataset.name : ''}
        className="max-w-4xl"
      >
        {isLoading ? (
          <div className="py-8 text-center text-sm text-[--txt-3]">Загрузка…</div>
        ) : !data || (data.photos.length === 0 && data.videos.length === 0) ? (
          <div className="py-8 text-center text-sm text-[--txt-3]">Датасет пуст</div>
        ) : (
          <div className="max-h-[70vh] space-y-5 overflow-auto">
            {data.photos.length > 0 && (
              <section>
                <h4 className="mb-2 text-xs font-medium text-[--txt-2]">
                  Фото · {data.photos.length}
                </h4>
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6">
                  {data.photos.map((p, idx) => (
                    <button
                      key={p.name}
                      type="button"
                      onClick={() => setLightboxIndex(idx)}
                      className="group relative block overflow-hidden rounded-lg border border-[--line-1] bg-[--bg-2] transition-shadow hover:shadow-[--shadow-card]"
                      title={p.name}
                    >
                      <PreviewImage
                        src={dataset ? datasetFileUrl(dataset.id, p.name) : ''}
                        alt={p.name}
                        className="aspect-square w-full object-cover transition-transform group-hover:scale-105"
                      />
                      <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all group-hover:bg-black/40 group-hover:opacity-100">
                        <ZoomIn className="h-6 w-6 text-white drop-shadow-md" />
                      </div>
                      <div className="pointer-events-none absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/80 to-transparent px-1.5 py-1 text-[10px] text-white">
                        {p.name}
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            )}
            {data.videos.length > 0 && (
              <section>
                <h4 className="mb-2 text-xs font-medium text-[--txt-2]">
                  Видео · {data.videos.length}
                </h4>
                <ul className="space-y-1 text-xs text-[--txt-2]">
                  {data.videos.map((v) => (
                    <li
                      key={v.name}
                      className="flex items-center justify-between rounded-md border border-[--line-1] bg-[--bg-2] px-2 py-1.5"
                    >
                      <span className="truncate">{v.name}</span>
                      <span className="text-[10px] text-[--txt-3]">
                        {(v.size / 1024 / 1024).toFixed(1)} MB
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </Modal>

      <Lightbox
        photos={photoUrls}
        index={lightboxIndex}
        onChange={setLightboxIndex}
        onClose={() => setLightboxIndex(null)}
      />
    </>
  )
}

function PreviewImage({
  src,
  alt,
  className,
}: {
  src: string
  alt: string
  className?: string
}) {
  const [failed, setFailed] = useState(false)

  const finalClass = cn('h-full w-full rounded-lg object-cover', className)

  if (failed) {
    return (
      <div
        className={cn(
          finalClass,
          'flex items-center justify-center bg-[--bg-3] text-[10px] text-[--txt-3]',
        )}
      >
        не удалось
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      draggable={false}
      onError={() => setFailed(true)}
      className={finalClass}
    />
  )
}

function Lightbox({
  photos,
  index,
  onChange,
  onClose,
}: {
  photos: { url: string; name: string }[]
  index: number | null
  onChange: (i: number | null) => void
  onClose: () => void
}) {
  useEffect(() => {
    if (index === null) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft' && photos.length)
        onChange((index - 1 + photos.length) % photos.length)
      if (e.key === 'ArrowRight' && photos.length)
        onChange((index + 1) % photos.length)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [index, photos.length, onChange, onClose])

  if (index === null || photos.length === 0) return null
  const cur = photos[Math.min(index, photos.length - 1)]
  if (!cur) return null

  return createPortal(
    <AnimatePresence>
      <motion.div
        key="lightbox"
        className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/95 backdrop-blur-md"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.img
          key={cur.url}
          src={cur.url}
          alt={cur.name}
          draggable={false}
          initial={{ scale: 0.96, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.96, opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={(e) => e.stopPropagation()}
          className="max-h-[92vh] max-w-[92vw] rounded-xl object-contain shadow-2xl"
        />

        <button
          type="button"
          aria-label="Закрыть"
          onClick={onClose}
          className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
        >
          <X className="h-5 w-5" />
        </button>

        {photos.length > 1 && (
          <>
            <button
              type="button"
              aria-label="Предыдущее"
              onClick={(e) => {
                e.stopPropagation()
                onChange((index - 1 + photos.length) % photos.length)
              }}
              className="absolute left-4 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
            <button
              type="button"
              aria-label="Следующее"
              onClick={(e) => {
                e.stopPropagation()
                onChange((index + 1) % photos.length)
              }}
              className="absolute right-4 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          </>
        )}

        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-white/10 px-3 py-1 text-xs text-white">
          {cur.name} · {index + 1} / {photos.length}
        </div>
      </motion.div>
    </AnimatePresence>,
    document.body,
  )
}

function WearMapModal({
  dataset,
  onClose,
}: {
  dataset: DatasetRow | null
  onClose: () => void
}) {
  const entries = useMemo(() => {
    if (!dataset?.wear_map) return [] as Array<[string, number]>
    return Object.entries(dataset.wear_map).sort((a, b) => b[1] - a[1])
  }, [dataset])

  const maxWear = entries.length ? Math.max(...entries.map(([, v]) => v), 1) : 1

  return (
    <Modal
      open={dataset !== null}
      onClose={onClose}
      title={dataset ? `Wear Map · ${dataset.name}` : ''}
      className="max-w-2xl"
    >
      {entries.length === 0 ? (
        <div className="py-8 text-center text-sm text-[--txt-3]">
          Нет данных об использовании
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-1">
          {entries.map(([key, value]) => {
            const intensity = value / maxWear
            return (
              <div
                key={key}
                title={`${key}: ${value}`}
                className="aspect-square rounded border border-[--line-1]"
                style={{
                  backgroundColor: `color-mix(in srgb, var(--blue) ${Math.round(
                    intensity * 100,
                  )}%, var(--bg-3))`,
                }}
              />
            )
          })}
        </div>
      )}
      <div className="mt-4 flex items-center justify-between text-xs text-[--txt-3]">
        <span>Меньше</span>
        <div className="flex gap-0.5">
          {[0.1, 0.3, 0.5, 0.7, 1.0].map((i) => (
            <div
              key={i}
              className="h-3 w-3 rounded-sm border border-[--line-1]"
              style={{
                backgroundColor: `color-mix(in srgb, var(--blue) ${Math.round(
                  i * 100,
                )}%, var(--bg-3))`,
              }}
            />
          ))}
        </div>
        <span>Больше</span>
      </div>
    </Modal>
  )
}

function LinkModal({
  dataset,
  devices,
  onClose,
  onLinked,
}: {
  dataset: DatasetRow | null
  devices: Device[]
  onClose: () => void
  onLinked: () => void
}) {
  const [deviceId, setDeviceId] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!dataset || !deviceId) return
    setBusy(true)
    try {
      await linkDataset(dataset.id, deviceId)
      toast.success('Датасет привязан')
      onLinked()
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={dataset !== null}
      onClose={onClose}
      title={dataset ? `Привязка · ${dataset.name}` : ''}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="primary" onClick={submit} disabled={!deviceId || busy}>
            Привязать
          </Button>
        </>
      }
    >
      <label className="mb-1 block text-xs text-[--txt-2]">Устройство</label>
      <select
        value={deviceId}
        onChange={(e) => setDeviceId(e.target.value)}
        className="w-full rounded-md border border-[--line-2] bg-[--bg-1] px-3 py-2 text-sm text-[--txt-1] focus:outline-none focus:ring-2 focus:ring-[--blue]"
      >
        <option value="">— выберите устройство —</option>
        {devices?.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name} {d.phone_number ? `(${d.phone_number})` : ''}
          </option>
        ))}
      </select>
    </Modal>
  )
}

function UploadModal({
  open,
  devices,
  onClose,
  onUploaded,
}: {
  open: boolean
  devices: Device[]
  onClose: () => void
  onUploaded: () => void
}) {
  const [name, setName] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [deviceId, setDeviceId] = useState('')
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const reset = () => {
    setName('')
    setFiles([])
    setDeviceId('')
  }

  const handleClose = () => {
    if (busy) return
    reset()
    onClose()
  }

  const submit = async () => {
    if (!name.trim() || files.length === 0) return
    setBusy(true)
    try {
      await uploadDataset(name.trim(), files, deviceId || undefined)
      toast.success(`Загружено ${files.length} файл(ов)`)
      reset()
      onUploaded()
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Новый датасет"
      footer={
        <>
          <Button variant="ghost" onClick={handleClose} disabled={busy}>
            Отмена
          </Button>
          <Button
            variant="primary"
            onClick={submit}
            disabled={!name.trim() || files.length === 0 || busy}
          >
            Загрузить
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-xs text-[--txt-2]">Название</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Например: summer_2026"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs text-[--txt-2]">Устройство (опционально)</label>
          <select
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
            className="w-full rounded-md border border-[--line-2] bg-[--bg-1] px-3 py-2 text-sm text-[--txt-1] focus:outline-none focus:ring-2 focus:ring-[--blue]"
          >
            <option value="">— не привязывать —</option>
            {devices?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-xs text-[--txt-2]">Файлы</label>
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              setFiles(Array.from(e.dataTransfer.files))
            }}
            className="flex h-32 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-[--line-2] text-xs hover:border-[--blue] hover:bg-[--blue]/5"
          >
            <FolderOpen className="mb-1 h-5 w-5 text-[--txt-2]" />
            {files.length > 0 ? (
              <span className="text-[--txt-1]">Выбрано {files.length} файл(ов)</span>
            ) : (
              <span className="text-[--txt-3]">Выбрать или перетащить</span>
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
        </div>
      </div>
    </Modal>
  )
}
