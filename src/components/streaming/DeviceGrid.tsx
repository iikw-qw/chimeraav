// DeviceGrid — responsive grid of DeviceStream tiles with click-to-fullscreen
// and IntersectionObserver-based lazy activation. Streams that are scrolled
// off-screen pause their decoder & socket.

import { useCallback, useEffect, useRef, useState } from 'react'
import { DeviceStream } from './DeviceStream'
import { FullscreenView } from './FullscreenView'

export interface DeviceGridItem {
  id: string
  title: string
}

export interface DeviceGridProps {
  devices: DeviceGridItem[]
  columns?: number
}

export function DeviceGrid({ devices, columns = 3 }: DeviceGridProps) {
  const [fullscreen, setFullscreen] = useState<DeviceGridItem | null>(null)
  const [visibleIds, setVisibleIds] = useState<Set<string>>(new Set())
  const itemsRef = useRef<Map<string, HTMLDivElement>>(new Map())
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') {
      // Fallback: assume everything is visible.
      setVisibleIds(new Set(devices.map((d) => d.id)))
      return
    }
    observerRef.current = new IntersectionObserver(
      (entries) => {
        setVisibleIds((prev) => {
          const next = new Set(prev)
          let changed = false
          for (const entry of entries) {
            const id = (entry.target as HTMLElement).dataset.deviceId
            if (!id) continue
            if (entry.isIntersecting) {
              if (!next.has(id)) {
                next.add(id)
                changed = true
              }
            } else if (next.has(id)) {
              next.delete(id)
              changed = true
            }
          }
          return changed ? next : prev
        })
      },
      { root: null, rootMargin: '120px', threshold: 0.05 },
    )
    return () => {
      observerRef.current?.disconnect()
      observerRef.current = null
    }
  }, [devices])

  const setItemRef = useCallback((id: string, el: HTMLDivElement | null) => {
    const map = itemsRef.current
    const obs = observerRef.current
    const prev = map.get(id)
    if (prev && obs) obs.unobserve(prev)
    if (el) {
      map.set(id, el)
      if (obs) obs.observe(el)
    } else {
      map.delete(id)
    }
  }, [])

  return (
    <>
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {devices.map((d) => (
          <div
            key={d.id}
            ref={(el) => setItemRef(d.id, el)}
            data-device-id={d.id}
          >
            <DeviceStream
              deviceId={d.id}
              title={d.title}
              active={visibleIds.has(d.id)}
              onFullscreen={() => setFullscreen(d)}
            />
          </div>
        ))}
        {devices.length === 0 && (
          <div className="col-span-full grid place-items-center py-16 text-sm text-[--text-3]">
            Нет активных стримов. Запустите Chimera-агент на телефоне.
          </div>
        )}
      </div>
      {fullscreen && (
        <FullscreenView
          deviceId={fullscreen.id}
          title={fullscreen.title}
          onClose={() => setFullscreen(null)}
        />
      )}
    </>
  )
}
