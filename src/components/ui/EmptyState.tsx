import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface EmptyStateProps {
  icon: ReactNode
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 px-6 py-16 text-center',
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center text-[--txt-3] [&>svg]:h-12 [&>svg]:w-12">
        {icon}
      </div>
      <div className="text-lg font-medium text-[--txt-1]">{title}</div>
      {description && (
        <div className="max-w-sm text-sm text-[--txt-2]">{description}</div>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
