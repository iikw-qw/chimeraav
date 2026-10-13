import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

export interface Connection {
  id: string
  datasetId: string
  deviceId: string
}

export interface ConnectionCanvasProps {
  connections: Connection[]
  containerRef: React.RefObject<HTMLElement>
  getDatasetAnchor?: (datasetId: string) => DOMRect | null
  onRemove?: (connection: Connection) => void
}

interface Resolved extends Connection {
  x1: number
  y1: number
  x2: number
  y2: number
}

export function ConnectionCanvas({
  connections,
  containerRef,
  getDatasetAnchor,
  onRemove,
}: ConnectionCanvasProps) {
  const [resolved, setResolved] = useState<Resolved[]>([])
  const [hoverId, setHoverId] = useState<string | null>(null)
  const rafRef = useRef<number | null>(null)

  const compute = () => {
    const container = containerRef.current
    if (!container) return
    const crect = container.getBoundingClientRect()
    const out: Resolved[] = []
    for (const c of connections) {
      const cell = container.querySelector<HTMLElement>(
        `[data-device-id="${c.deviceId}"]`,
      )
      const dsRect = getDatasetAnchor?.(c.datasetId) ?? null
      if (!cell || !dsRect) continue
      const cellR = cell.getBoundingClientRect()
      out.push({
        ...c,
        x1: dsRect.left + dsRect.width / 2 - crect.left,
        y1: dsRect.top + dsRect.height / 2 - crect.top,
        x2: cellR.left + cellR.width / 2 - crect.left,
        y2: cellR.top + cellR.height / 2 - crect.top,
      })
    }
    setResolved(out)
  }

  useLayoutEffect(() => {
    compute()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connections])

  useEffect(() => {
    const tick = () => {
      compute()
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connections])

  return (
    <svg className="pointer-events-none absolute inset-0 z-20 h-full w-full">
      <defs>
        <linearGradient id="chimera-conn-grad" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#A78BFA" />
          <stop offset="100%" stopColor="#5B9BFF" />
        </linearGradient>
      </defs>
      {resolved.map((c) => {
        const dx = c.x2 - c.x1
        const c1x = c.x1 + dx * 0.5
        const c2x = c.x2 - dx * 0.5
        const d = `M ${c.x1} ${c.y1} C ${c1x} ${c.y1}, ${c2x} ${c.y2}, ${c.x2} ${c.y2}`
        const midX = (c.x1 + c.x2) / 2
        const midY = (c.y1 + c.y2) / 2
        const isHover = hoverId === c.id
        return (
          <g key={c.id} className="pointer-events-auto">
            <path
              d={d}
              stroke="transparent"
              strokeWidth={16}
              fill="none"
              onMouseEnter={() => setHoverId(c.id)}
              onMouseLeave={() => setHoverId((h) => (h === c.id ? null : h))}
            />
            <path
              d={d}
              stroke="url(#chimera-conn-grad)"
              strokeWidth={isHover ? 2.5 : 1.5}
              fill="none"
              opacity={isHover ? 1 : 0.7}
            />
            {isHover && (
              <foreignObject
                x={midX - 10}
                y={midY - 10}
                width={20}
                height={20}
                onMouseEnter={() => setHoverId(c.id)}
                onMouseLeave={() => setHoverId(null)}
              >
                <button
                  onClick={() => onRemove?.(c)}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-[--red] text-white shadow"
                >
                  <X className="h-3 w-3" />
                </button>
              </foreignObject>
            )}
          </g>
        )
      })}
    </svg>
  )
}
