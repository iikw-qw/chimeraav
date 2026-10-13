import { useEffect, useState } from 'react'
import { Minus, Square, X } from 'lucide-react'
import { cn } from '../../lib/cn'

export function TitleBar() {
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    let cancelled = false
    window.chimera?.window
      .isMaximized()
      .then((v) => {
        if (!cancelled) setMaximized(v)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const onMinimize = () => window.chimera?.window.minimize()
  const onMaximize = async () => {
    await window.chimera?.window.maximize()
    const m = await window.chimera?.window.isMaximized()
    setMaximized(!!m)
  }
  const onClose = () => window.chimera?.window.close()

  return (
    <div className="drag-region flex h-10 items-center justify-between border-b border-[--line-1] bg-[--bg-1] px-4 select-none">
      <div className="flex items-center gap-2">
        <img
          src={new URL('../../assets/chimera-logo.png', import.meta.url).href}
          alt="Chimera"
          className="h-[22px] w-[22px] rounded-md object-cover"
        />
        <span className="font-display text-xs font-semibold tracking-[0.2em] text-[--txt-2]">
          CHIMERA
        </span>
      </div>

      <div className="no-drag flex items-center">
        <TitleButton onClick={onMinimize} aria-label="Minimize">
          <Minus className="h-3.5 w-3.5" />
        </TitleButton>
        <TitleButton onClick={onMaximize} aria-label={maximized ? 'Restore' : 'Maximize'}>
          <Square className="h-3 w-3" />
        </TitleButton>
        <TitleButton
          onClick={onClose}
          aria-label="Close"
          className="hover:!bg-[--red] hover:!text-white"
        >
          <X className="h-3.5 w-3.5" />
        </TitleButton>
      </div>
    </div>
  )
}

function TitleButton({
  children,
  className,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        'flex h-10 w-11 items-center justify-center text-[--txt-2] transition-colors hover:bg-[--bg-3] hover:text-[--txt-1]',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
