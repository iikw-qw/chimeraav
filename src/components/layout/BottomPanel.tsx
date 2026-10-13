import { useEffect, useRef, useState, type PointerEvent } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '../../lib/cn'
import {
  BOTTOM_PANEL_COLLAPSED,
  BOTTOM_PANEL_MIN,
  useAppStore,
} from '../../stores/appStore'
import { CommentsTab } from '../bottom-panel/CommentsTab'
import { WelcomeTab } from '../bottom-panel/WelcomeTab'

type TabKey = 'comments' | 'welcomes' | 'incoming' | 'logs'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'comments', label: 'Комментарии' },
  { key: 'welcomes', label: 'Приветствия' },
  { key: 'incoming', label: 'Входящие' },
  { key: 'logs', label: 'Логи' },
]

export function BottomPanel() {
  const height = useAppStore((s) => s.bottomPanelHeight)
  const collapsed = useAppStore((s) => s.bottomPanelCollapsed)
  const setHeight = useAppStore((s) => s.setBottomPanelHeight)
  const toggle = useAppStore((s) => s.toggleBottomPanel)

  const [tab, setTab] = useState<TabKey>('comments')
  const dragState = useRef<{ startY: number; startH: number } | null>(null)

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    dragState.current = { startY: e.clientY, startH: height }
  }
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const st = dragState.current
    if (!st) return
    const delta = st.startY - e.clientY
    setHeight(st.startH + delta)
  }
  const onPointerUp = (e: PointerEvent<HTMLDivElement>) => {
    dragState.current = null
    try {
      ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
    } catch {
      // no-op
    }
  }

  useEffect(() => {
    const onResize = () => {
      const maxH = Math.floor(window.innerHeight * 0.5)
      if (height > maxH) setHeight(maxH)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [height, setHeight])

  const bodyHidden = collapsed || height <= BOTTOM_PANEL_COLLAPSED + 4

  return (
    <div
      className="flex shrink-0 flex-col border-t border-[--line-1] bg-[--bg-1]"
      style={{ height: Math.max(BOTTOM_PANEL_MIN, height) }}
    >
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        className="flex h-3 cursor-ns-resize items-center justify-center"
      >
        <div className="my-1 h-1 w-12 rounded-full bg-[--line-2]" />
      </div>

      <div className="flex h-9 items-center border-b border-[--line-1] px-2">
        <div className="flex items-center gap-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                'h-8 border-b-2 px-3 text-xs transition-colors',
                tab === t.key
                  ? 'border-[--blue] text-[--blue]'
                  : 'border-transparent text-[--txt-2] hover:text-[--txt-1]',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? 'Expand panel' : 'Collapse panel'}
          className="ml-auto flex h-7 w-7 items-center justify-center rounded-md text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]"
        >
          {collapsed ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
      </div>

      {!bodyHidden && (
        <div className="flex-1 overflow-auto p-3 text-xs text-[--txt-3]">
          <TabContent tab={tab} />
        </div>
      )}
    </div>
  )
}

function TabContent({ tab }: { tab: TabKey }) {
  switch (tab) {
    case 'comments':
      return <CommentsTab />
    case 'welcomes':
      return <WelcomeTab />
    case 'incoming':
      return <div>Входящие сообщения будут здесь.</div>
    case 'logs':
      return <div>Стрим логов будет здесь.</div>
  }
}
