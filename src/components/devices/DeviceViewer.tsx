import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft,
  ChevronsDown,
  ChevronsUp,
  Circle,
  Fingerprint,
  Flame,
  ImageOff,
  Power,
  RotateCcw,
  Square,
  X,
} from 'lucide-react'
import { Button } from '../ui'
import { useQueryClient } from '@tanstack/react-query'
import {
  DEVICES_QUERY_KEY,
  galleryCleanup,
  getDeviceInfo,
  humanSwipeDevice,
  humanTapDevice,
  humanTypeDevice,
  keyDevice,
  refreshDeviceIp,
  setCursorTrail,
  startWarmup,
  streamUrl,
  type CursorEvent,
  type Device,
  type DeviceInfo,
} from '../../hooks/useDevices'
import { ws } from '../../api/ws'
import { toast } from '../../hooks/useToast'
import { useSettings } from '../../hooks/useSettings'

interface Props {
  device: Device | null
  onClose: () => void
}

const ANDROID_KEYS = {
  home: 3,
  back: 4,
  menu: 82,
  recent: 187,
  power: 26,
  volumeUp: 24,
  volumeDown: 25,
}

type CursorTrailDot = { id: number; x: number; y: number; until: number; kind: 'tap' | 'swipe' }

export function DeviceViewer({ device, onClose }: Props) {
  const [streamKey, setStreamKey] = useState(() => Date.now())
  const [info, setInfo] = useState<DeviceInfo | null>(null)
  const [imgLoaded, setImgLoaded] = useState(false)
  const [natural, setNatural] = useState<{ w: number; h: number }>({ w: 1080, h: 1920 })
  const [pending, setPending] = useState<null | { x1: number; y1: number; t: number }>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const [typing, setTyping] = useState('')
  const [cursorTrail, setCursorTrailState] = useState<CursorTrailDot[]>([])
  const [nativePointer, setNativePointer] = useState(false)
  const { data: settings = {} } = useSettings()
  const showOverlay = (settings.cursor_overlay ?? true) as boolean
  const useHumanInput = (settings.human_input_enabled ?? true) as boolean
  const streamPreset = (settings.stream_preset ?? 'smooth') as
    | 'smooth'
    | 'balanced'
    | 'quality'

  const open = device !== null

  useEffect(() => {
    if (!open) return
    setInfo(null)
    setImgLoaded(false)
    setStreamKey(Date.now())
  }, [device?.id, open])

  useEffect(() => {
    if (!device) return
    let cancelled = false
    void (async () => {
      try {
        const i = await getDeviceInfo(device.id)
        if (!cancelled) setInfo(i)
      } catch {
        // non-fatal
      }
    })()
    return () => {
      cancelled = true
    }
  }, [device?.id])


  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Live cursor overlay — subscribes to the "cursor" WS channel and animates
  // a finger dot along the bezier waypoints broadcast by the backend.
  useEffect(() => {
    if (!open || !device) return
    let alive = true
    let counter = 0

    const drop = (dots: CursorTrailDot[]) =>
      dots.filter((d) => d.until > performance.now())

    const timer = setInterval(() => {
      if (!alive) return
      setCursorTrailState((cur) => drop(cur))
    }, 80)

    const handler = (raw: unknown) => {
      const ev = raw as CursorEvent
      if (!ev || ev.device_id !== device.id) return
      const now = performance.now()
      if (ev.kind === 'tap' && ev.x != null && ev.y != null) {
        const id = ++counter
        const dot: CursorTrailDot = {
          id,
          x: ev.x,
          y: ev.y,
          until: now + Math.max(320, (ev.duration_ms ?? 120) + 400),
          kind: 'tap',
        }
        setCursorTrailState((cur) => [...drop(cur), dot])
        return
      }
      if (ev.kind === 'swipe' && ev.waypoints && ev.waypoints.length > 0) {
        // Schedule each waypoint so the dot "walks" the bezier in real time.
        ev.waypoints.forEach((wp, idx) => {
          setTimeout(() => {
            if (!alive) return
            const id = ++counter
            const dot: CursorTrailDot = {
              id,
              x: wp.x,
              y: wp.y,
              until: performance.now() + (idx === (ev.waypoints!.length - 1) ? 400 : 160),
              kind: 'swipe',
            }
            setCursorTrailState((cur) => [...drop(cur), dot])
          }, wp.t_ms)
        })
      }
    }

    const unsub = ws.subscribe('cursor', handler)
    return () => {
      alive = false
      clearInterval(timer)
      unsub()
    }
  }, [open, device?.id])

  const imgSrc = useMemo(() => {
    if (!device) return undefined
    // smooth   — high fps, smaller frame, faster encode  (default for laggy hosts)
    // balanced — middle ground
    // quality  — bigger frame, lower fps                  (sharp text, slower)
    const params =
      streamPreset === 'quality'
        ? { fps: 24, quality: 80, maxWidth: 720 }
        : streamPreset === 'balanced'
          ? { fps: 30, quality: 72, maxWidth: 600 }
          : { fps: 42, quality: 60, maxWidth: 420 }
    return `${streamUrl(device.id, params)}&k=${streamKey}`
  }, [device?.id, streamKey, streamPreset])

  const mapCoords = (e: MouseEvent<HTMLImageElement>) => {
    const img = imgRef.current
    if (!img) return null
    const rect = img.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * natural.w
    const y = ((e.clientY - rect.top) / rect.height) * natural.h
    return { x: Math.round(x), y: Math.round(y) }
  }

  const handlePointerDown = (e: MouseEvent<HTMLImageElement>) => {
    if (!device) return
    const coords = mapCoords(e)
    if (!coords) return
    setPending({ x1: coords.x, y1: coords.y, t: Date.now() })
  }

  const handlePointerUp = async (e: MouseEvent<HTMLImageElement>) => {
    if (!device || !pending) {
      setPending(null)
      return
    }
    const coords = mapCoords(e)
    setPending(null)
    if (!coords) return
    const dx = coords.x - pending.x1
    const dy = coords.y - pending.y1
    const dist = Math.hypot(dx, dy)
    try {
      if (dist < 12) {
        await humanTapDevice(device.id, coords.x, coords.y)
      } else {
        await humanSwipeDevice(device.id, pending.x1, pending.y1, coords.x, coords.y)
      }
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const sendKey = async (code: number) => {
    if (!device) return
    try {
      await keyDevice(device.id, code)
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const sendText = async () => {
    if (!device || !typing.trim()) return
    try {
      if (useHumanInput) {
        await humanTypeDevice(device.id, typing)
      } else {
        await humanTypeDevice(device.id, typing) // keep single code path; backend handles both
      }
      setTyping('')
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const toggleNativePointer = async () => {
    if (!device) return
    try {
      const next = !nativePointer
      await setCursorTrail(device.id, next)
      setNativePointer(next)
      toast.success(next ? 'Касания видны на устройстве' : 'Нативный курсор выключен')
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const [warmupBusy, setWarmupBusy] = useState(false)
  const [galleryBusy, setGalleryBusy] = useState(false)

  const triggerWarmup = async () => {
    if (!device || warmupBusy) return
    setWarmupBusy(true)
    try {
      const r = await startWarmup(device.id, { duration_seconds: 300 })
      toast.success(`Прогрев запущен (${r.duration_seconds}s)`)
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setWarmupBusy(false)
    }
  }

  const triggerGalleryCleanup = async () => {
    if (!device || galleryBusy) return
    if (!confirm('Удалить все ранее загруженные файлы Chimera из галереи?')) return
    setGalleryBusy(true)
    try {
      const r = await galleryCleanup(device.id)
      toast.success(`Удалено файлов: ${r.removed}`)
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setGalleryBusy(false)
    }
  }

  return createPortal(
    <AnimatePresence>
      {open && device && (
        <motion.div
          className="fixed inset-0 z-50 flex bg-black/90 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <button
            type="button"
            aria-label="Закрыть"
            onClick={onClose}
            className="absolute right-4 top-4 z-10 rounded-md bg-black/50 p-2 text-white transition hover:bg-black/70"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="flex flex-1 items-center justify-center p-6">
            <div className="relative flex max-h-full max-w-full items-center justify-center">
              {device.status === 'unauthorized' ? (
                <div className="rounded-xl border border-[--amber]/50 bg-[--bg-2] p-6 text-center text-[--txt-2]">
                  <p className="mb-2 font-medium text-[--amber]">Устройство не авторизовано</p>
                  <p className="text-sm">На телефоне нажмите «Разрешить отладку по USB».</p>
                </div>
              ) : (
                <>
                  {!imgLoaded && (
                    <div className="absolute inset-0 flex items-center justify-center text-sm text-[--txt-3]">
                      Загрузка экрана…
                    </div>
                  )}
                  <div className="relative">
                    <img
                      ref={imgRef}
                      src={imgSrc}
                      alt={device.name}
                      draggable={false}
                      decoding="async"
                      onLoad={(e) => {
                        setImgLoaded(true)
                        const t = e.currentTarget
                        if (t.naturalWidth > 0) {
                          setNatural({ w: t.naturalWidth, h: t.naturalHeight })
                        }
                      }}
                      onMouseDown={handlePointerDown}
                      onMouseUp={handlePointerUp}
                      className="max-h-[calc(100vh-80px)] max-w-full cursor-crosshair select-none rounded-xl border border-[--line-2] shadow-2xl"
                    />
                    {showOverlay && imgLoaded && cursorTrail.length > 0 && (
                      <CursorOverlay
                        dots={cursorTrail}
                        natural={natural}
                        imgEl={imgRef.current}
                      />
                    )}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="flex w-80 flex-col border-l border-[--line-1] bg-[--bg-1]">
            <div className="border-b border-[--line-1] p-4">
              <div className="truncate text-base font-semibold text-[--txt-1]">{device.name}</div>
              <div className="mt-1 flex items-center gap-2 text-xs text-[--txt-3]">
                <span className="capitalize">{device.platform}</span>
                <span>·</span>
                <span>{device.status}</span>
                {device.battery_level != null && (
                  <>
                    <span>·</span>
                    <span>{device.battery_level}%</span>
                  </>
                )}
              </div>
              <IpRow device={device} />
            </div>

            <div className="space-y-2 p-4">
              <div className="text-xs font-medium text-[--txt-2]">Управление</div>
              <div className="grid grid-cols-3 gap-2">
                <Button variant="secondary" size="sm" onClick={() => sendKey(ANDROID_KEYS.back)}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Button variant="secondary" size="sm" onClick={() => sendKey(ANDROID_KEYS.home)}>
                  <Circle className="h-4 w-4" />
                </Button>
                <Button variant="secondary" size="sm" onClick={() => sendKey(ANDROID_KEYS.recent)}>
                  <Square className="h-4 w-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => sendKey(ANDROID_KEYS.volumeUp)}
                >
                  <ChevronsUp className="h-4 w-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => sendKey(ANDROID_KEYS.volumeDown)}
                >
                  <ChevronsDown className="h-4 w-4" />
                </Button>
                <Button variant="secondary" size="sm" onClick={() => sendKey(ANDROID_KEYS.power)}>
                  <Power className="h-4 w-4" />
                </Button>
              </div>
              <Button
                variant={nativePointer ? 'primary' : 'secondary'}
                size="sm"
                onClick={toggleNativePointer}
                leftIcon={<Fingerprint className="h-4 w-4" />}
                className="w-full"
              >
                {nativePointer ? 'Касания видны' : 'Показать касания'}
              </Button>

              <div className="grid grid-cols-2 gap-2 pt-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={triggerWarmup}
                  disabled={warmupBusy || device.platform !== 'android'}
                  leftIcon={<Flame className="h-4 w-4" />}
                >
                  {warmupBusy ? 'Запуск…' : 'Прогрев 5м'}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={triggerGalleryCleanup}
                  disabled={galleryBusy || device.platform !== 'android'}
                  leftIcon={<ImageOff className="h-4 w-4" />}
                >
                  {galleryBusy ? 'Очистка…' : 'Очистить галерею'}
                </Button>
              </div>
            </div>

            <div className="space-y-2 p-4">
              <div className="text-xs font-medium text-[--txt-2]">Ввод текста</div>
              <div className="flex gap-2">
                <input
                  value={typing}
                  onChange={(e) => setTyping(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      void sendText()
                    }
                  }}
                  placeholder="Введите текст…"
                  className="flex-1 rounded-md border border-[--line-2] bg-[--bg-2] px-2 py-1.5 text-xs text-[--txt-1] outline-none focus:border-[--blue]"
                />
                <Button variant="primary" size="sm" onClick={sendText} disabled={!typing.trim()}>
                  Отправить
                </Button>
              </div>
            </div>

            <div className="flex-1 space-y-2 overflow-auto border-t border-[--line-1] p-4">
              <div className="text-xs font-medium text-[--txt-2]">Информация</div>
              {info ? (
                <InfoGrid info={info} device={device} />
              ) : (
                <div className="text-xs text-[--txt-3]">Загрузка…</div>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-[--line-1] p-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setStreamKey(Date.now())}
                leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
              >
                Пересоединить
              </Button>
              <Button variant="secondary" size="sm" onClick={onClose}>
                Закрыть
              </Button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

function CursorOverlay({
  dots,
  natural,
  imgEl,
}: {
  dots: CursorTrailDot[]
  natural: { w: number; h: number }
  imgEl: HTMLImageElement | null
}) {
  if (!imgEl || dots.length === 0) return null
  const rect = imgEl.getBoundingClientRect()
  const scaleX = rect.width / natural.w
  const scaleY = rect.height / natural.h

  const head = dots[dots.length - 1]
  const now = performance.now()

  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden rounded-xl"
      aria-hidden
    >
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 ${rect.width} ${rect.height}`}
        preserveAspectRatio="none"
      >
        {dots.slice(0, -1).map((d) => {
          const alpha = Math.max(0, (d.until - now) / 320)
          return (
            <circle
              key={d.id}
              cx={d.x * scaleX}
              cy={d.y * scaleY}
              r={3}
              fill="rgba(96,165,250,0.6)"
              opacity={alpha}
            />
          )
        })}
      </svg>
      <motion.div
        key={head.id}
        className="absolute"
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.6 }}
        transition={{ duration: 0.12, ease: 'easeOut' }}
        style={{
          left: head.x * scaleX - 14,
          top: head.y * scaleY - 14,
          width: 28,
          height: 28,
        }}
      >
        <div
          className="h-full w-full rounded-full border-2 border-white/80 shadow-lg"
          style={{
            background:
              'radial-gradient(circle at 35% 30%, rgba(255,255,255,0.95), rgba(96,165,250,0.55) 55%, rgba(37,99,235,0.35))',
            boxShadow:
              '0 0 0 4px rgba(96,165,250,0.25), 0 0 18px rgba(96,165,250,0.7)',
          }}
        />
        {head.kind === 'tap' && (
          <motion.div
            className="absolute inset-0 rounded-full border-2 border-[rgba(96,165,250,0.9)]"
            initial={{ scale: 1, opacity: 0.9 }}
            animate={{ scale: 2.4, opacity: 0 }}
            transition={{ duration: 0.45, ease: 'easeOut' }}
          />
        )}
      </motion.div>
    </div>
  )
}

function IpRow({ device }: { device: Device }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const refresh = async () => {
    if (busy) return
    setBusy(true)
    try {
      await refreshDeviceIp(device.id)
    } catch {
      toast.danger('Не удалось получить IP устройства')
    } finally {
      qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
      setBusy(false)
    }
  }
  return (
    <div
      className="mt-1 flex items-center justify-between gap-2"
      title="Внешний IP — для проверки прокси/VPN"
    >
      <div className="truncate font-mono text-[11px] text-[--txt-3]">
        IP: {device.ip_address ?? '—'}
      </div>
      <button
        type="button"
        onClick={refresh}
        disabled={busy}
        className="rounded-md border border-[--line-1] px-2 py-0.5 text-[10px] text-[--txt-2] transition-colors hover:bg-[--bg-3] disabled:opacity-60"
      >
        {busy ? '…' : 'Обновить'}
      </button>
    </div>
  )
}

function InfoGrid({ info, device }: { info: DeviceInfo; device: Device }) {
  const rows: [string, string | number | null | undefined][] = [
    ['Код', device.unique_code],
    ['Serial', device.serial],
    ['Модель', info.model],
    ['Производитель', info.manufacturer],
    ['Бренд', info.brand],
    ['Android', info.android_version],
    ['SDK', info.sdk],
    ['Разрешение', info.resolution],
    ['Батарея', info.battery_level != null ? `${info.battery_level}%` : null],
    ['IP', device.ip_address],
  ]
  return (
    <dl className="space-y-1.5 text-xs">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3 border-b border-[--line-1]/40 pb-1">
          <dt className="text-[--txt-3]">{k}</dt>
          <dd className="truncate text-right text-[--txt-1]">{v ?? '—'}</dd>
        </div>
      ))}
    </dl>
  )
}
