import { useEffect, useMemo, useState, type MouseEvent } from 'react'
import { motion } from 'framer-motion'
import { Battery, Play } from 'lucide-react'
import { cn } from '../../lib/cn'
import { toast } from '../../hooks/useToast'
import { Badge, ContextMenu, type ContextMenuItem } from '../ui'
import { useAppStore } from '../../stores/appStore'
import { useQueryClient } from '@tanstack/react-query'
import {
  DEVICES_QUERY_KEY,
  installAgent,
  refreshDeviceIp,
  screenshotUrl,
  setMaster,
  streamUrl,
  type Device,
} from '../../hooks/useDevices'

export interface DeviceCellProps {
  device: Device
  index: number
  onOpenFullscreen?: (d: Device) => void
  onScreenshot?: (d: Device) => void
  onOpenProfile?: (d: Device) => void
  onLinkDataset?: (d: Device) => void
  onReboot?: (d: Device) => void
  onInfo?: (d: Device) => void
  onPauseToggle?: (d: Device) => void
  onDisconnect?: (d: Device) => void
}

function statusDotClass(status: string): string {
  switch (status) {
    case 'online':
      return 'bg-[--green] animate-[breathe_2s_infinite]'
    case 'error':
      return 'bg-[--red]'
    case 'warming':
      return 'bg-[--amber]'
    case 'unauthorized':
      return 'bg-[--amber] animate-[breathe_2s_infinite]'
    case 'offline':
      return 'bg-[--red]/60'
    default:
      return 'bg-[--txt-3]'
  }
}

export function DeviceCell({
  device,
  index,
  onOpenFullscreen,
  onScreenshot,
  onOpenProfile,
  onLinkDataset,
  onReboot,
  onInfo,
  onPauseToggle,
  onDisconnect,
}: DeviceCellProps) {
  const masterDeviceId = useAppStore((s) => s.masterDeviceId)
  const setMasterDeviceId = useAppStore((s) => s.setMasterDeviceId)
  const selectedDeviceIds = useAppStore((s) => s.selectedDeviceIds)
  const toggleDeviceSelected = useAppStore((s) => s.toggleDeviceSelected)
  const qc = useQueryClient()

  const [menu, setMenu] = useState<{ open: boolean; x: number; y: number }>({
    open: false,
    x: 0,
    y: 0,
  })
  const [installing, setInstalling] = useState(false)
  const [imgFailed, setImgFailed] = useState(false)
  const [streamKey, setStreamKey] = useState(() => Date.now())
  const [docVisible, setDocVisible] = useState(
    typeof document === 'undefined' ? true : document.visibilityState === 'visible',
  )

  useEffect(() => {
    const onVis = () => setDocVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  const isMaster = masterDeviceId === device.id || device.is_master
  const isSelected = selectedDeviceIds.has(device.id)

  useEffect(() => {
    if (device.status === 'online' || device.status === 'warming') {
      setImgFailed(false)
      setStreamKey(Date.now())
    }
  }, [device.status])

  const previewSrc = useMemo(() => {
    if (imgFailed) return undefined
    // Stop pumping MJPEG frames when the window is hidden — Chromium keeps
    // the connection open and renders into invisible memory otherwise, which
    // causes the runaway memory growth we saw after a few hours.
    if (!docVisible) return undefined
    if (device.status === 'online') {
      return `${streamUrl(device.id, { fps: 14, quality: 55, maxWidth: 260 })}&k=${streamKey}`
    }
    return `${screenshotUrl(device.id)}?t=${streamKey}`
  }, [device.id, device.status, imgFailed, streamKey, docVisible])

  const items: ContextMenuItem[] = useMemo(
    () => [
      { label: 'Открыть на весь экран', onSelect: () => onOpenFullscreen?.(device) },
      { label: 'Скриншот', onSelect: () => onScreenshot?.(device) },
      { label: 'Открыть профиль', onSelect: () => onOpenProfile?.(device) },
      { label: 'Привязать датасет', onSelect: () => onLinkDataset?.(device) },
      {
        label: 'Обновить IP (проверка прокси/VPN)',
        onSelect: async () => {
          try {
            await refreshDeviceIp(device.id)
          } finally {
            qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
          }
        },
      },
      {
        label: 'Запустить стриминг',
        onSelect: async () => {
          try {
            const res = await installAgent(device.id)
            if (res.ok) toast.success(res.message)
          } catch (e) {
            toast.danger((e as Error).message)
          }
        },
      },
      { separator: true, label: '' },
      { label: 'Перезагрузить', onSelect: () => onReboot?.(device) },
      { label: 'Прокси: US', disabled: true },
      { label: 'Информация', onSelect: () => onInfo?.(device) },
      { separator: true, label: '' },
      { label: 'Пауза/Возобновить', onSelect: () => onPauseToggle?.(device) },
      {
        label: 'Отключить',
        danger: true,
        onSelect: () => onDisconnect?.(device),
      },
    ],
    [
      device,
      qc,
      onDisconnect,
      onInfo,
      onLinkDataset,
      onOpenFullscreen,
      onOpenProfile,
      onPauseToggle,
      onReboot,
      onScreenshot,
    ],
  )

  const handleContextMenu = (e: MouseEvent) => {
    e.preventDefault()
    setMenu({ open: true, x: e.clientX, y: e.clientY })
  }

  const handleDoubleClick = async () => {
    setMasterDeviceId(device.id)
    try {
      await setMaster(device.id)
    } catch {
      // swallow — WS refresh will reconcile
    }
  }

  const handleClick = (e: MouseEvent) => {
    if (e.shiftKey || e.ctrlKey || e.metaKey) {
      toggleDeviceSelected(device.id)
      return
    }
    onOpenFullscreen?.(device)
  }

  return (
    <>
      <motion.div
        data-device-id={device.id}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.25,
          delay: Math.min(index * 0.015, 0.4),
          ease: 'easeOut',
        }}
        onContextMenu={handleContextMenu}
        onDoubleClick={handleDoubleClick}
        onClick={handleClick}
        className={cn(
          'group relative flex aspect-[9/16] cursor-pointer flex-col overflow-hidden rounded-xl border bg-[--bg-2] transition-all duration-200',
          'hover:scale-[1.02] hover:border-[--line-3] hover:shadow-[--shadow-card]',
          isSelected && 'border-[--blue] bg-[--blue-glow]',
          isMaster
            ? 'border-2 border-[--blue] shadow-[--glow-blue]'
            : !isSelected && 'border-[--line-1]',
        )}
      >
        <div className="relative flex-1 bg-black">
          {previewSrc ? (
            <img
              src={previewSrc}
              alt={device.name}
              className="h-full w-full object-cover"
              onError={() => setImgFailed(true)}
              draggable={false}
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-[--txt-3] text-xs">
              no preview
            </div>
          )}

          <span className="absolute left-1.5 top-1.5 rounded-md bg-black/60 px-1.5 text-[10px] font-medium text-white">
            #{index + 1}
          </span>

          <span
            className={cn(
              'absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full',
              statusDotClass(device.status),
            )}
          />

          <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1">
            <div className="truncate text-xs font-medium text-white">
              {device.name}
            </div>
          </div>
        </div>

        <div className="space-y-1 bg-[--bg-2] p-2">
          <div className="truncate text-xs font-medium text-[--txt-1]">
            {device.name}
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1 text-[10px] text-[--txt-2]">
              <Battery className="h-3 w-3" />
              <span>
                {device.battery_level != null ? `${device.battery_level}%` : '—'}
              </span>
            </div>
            {device.group_name && (
              <Badge variant="neutral" className="text-[10px]">
                {device.group_name}
              </Badge>
            )}
          </div>
          <div className="truncate text-[10px] text-[--txt-2]">
            {device.phone_number ?? device.platform}
          </div>
          {device.ip_address && (
            <div
              className="truncate font-mono text-[10px] text-[--txt-3]"
              title="Внешний IP (для проверки прокси/VPN)"
            >
              IP: {device.ip_address}
            </div>
          )}
          {device.platform === 'android' && (
            <button
              type="button"
              onClick={async (e) => {
                e.stopPropagation()
                setInstalling(true)
                try {
                  const res = await installAgent(device.id)
                  if (res.ok) toast.success(res.message)
                } catch (err) {
                  toast.danger((err as Error).message)
                } finally {
                  setInstalling(false)
                }
              }}
              disabled={installing}
              className="mt-1 flex w-full items-center justify-center gap-1 rounded bg-[--blue] px-2 py-1 text-[10px] font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
            >
              <Play className="h-2.5 w-2.5" />
              {installing ? 'Запуск...' : 'Стриминг'}
            </button>
          )}
        </div>
      </motion.div>

      <ContextMenu
        open={menu.open}
        x={menu.x}
        y={menu.y}
        items={items}
        onClose={() => setMenu((m) => ({ ...m, open: false }))}
      />
    </>
  )
}
