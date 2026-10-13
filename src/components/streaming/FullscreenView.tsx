// FullscreenView — modal for the focused device stream. Mounts a single
// DeviceStream sized to the viewport. Closes on Esc.

import { useEffect } from 'react'
import { X } from 'lucide-react'
import { DeviceStream } from './DeviceStream'

export interface FullscreenViewProps {
  deviceId: string
  title: string
  onClose: () => void
}

export function FullscreenView({ deviceId, title, onClose }: FullscreenViewProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 grid grid-rows-[auto_1fr] bg-black/90">
      <div className="flex items-center justify-between px-4 py-2 bg-black/70 text-white">
        <div className="font-medium truncate">{title}</div>
        <button
          type="button"
          onClick={onClose}
          className="grid place-items-center w-8 h-8 rounded-md hover:bg-white/10"
          title="Закрыть (Esc)"
        >
          <X size={16} />
        </button>
      </div>
      <div className="grid place-items-center p-4 overflow-hidden">
        <DeviceStream
          deviceId={deviceId}
          title={title}
          className="h-full w-auto max-w-full"
        />
      </div>
    </div>
  )
}
