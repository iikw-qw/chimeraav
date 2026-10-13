import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export function Skeleton({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'animate-shimmer rounded-lg bg-gradient-to-r from-[--bg-3] via-[--bg-2] to-[--bg-3] bg-[length:200%_100%]',
        className,
      )}
      {...rest}
    />
  )
}
