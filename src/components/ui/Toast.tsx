import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react'
import { useToast, type ToastStatus } from '../../hooks/useToast'
import { cn } from '../../lib/cn'

const STATUS_META: Record<
  ToastStatus,
  { border: string; icon: typeof Info; iconClass: string }
> = {
  success: {
    border: 'border-l-[--green]',
    icon: CheckCircle2,
    iconClass: 'text-[--green]',
  },
  warning: {
    border: 'border-l-[--amber]',
    icon: AlertTriangle,
    iconClass: 'text-[--amber]',
  },
  danger: {
    border: 'border-l-[--red]',
    icon: XCircle,
    iconClass: 'text-[--red]',
  },
  info: {
    border: 'border-l-[--blue]',
    icon: Info,
    iconClass: 'text-[--blue]',
  },
}

export function ToastViewport() {
  const toasts = useToast((s) => s.toasts)
  const dismiss = useToast((s) => s.dismiss)

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const meta = STATUS_META[t.status]
          const Icon = meta.icon
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ x: 100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 100, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className={cn(
                'pointer-events-auto flex items-start gap-3 rounded-lg border-l-4 bg-[--bg-2] border border-[--line-2] px-4 py-3 shadow-[var(--shadow-card)]',
                meta.border,
              )}
            >
              <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', meta.iconClass)} />
              <div className="min-w-0 flex-1">
                {t.title && (
                  <div className="text-sm font-medium text-[--txt-1]">{t.title}</div>
                )}
                <div className="text-xs text-[--txt-2] break-words">{t.message}</div>
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="rounded-md p-1 text-[--txt-3] hover:bg-[--bg-3] hover:text-[--txt-1] transition-colors"
                aria-label="Dismiss"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
