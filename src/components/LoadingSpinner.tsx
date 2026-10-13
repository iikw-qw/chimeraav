import { Loader2 } from 'lucide-react'
import { cn } from '../lib/cn'

interface Props {
  label?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' }

export function LoadingSpinner({ label, className, size = 'md' }: Props) {
  return (
    <div className={cn('flex items-center justify-center gap-2', className)}>
      <Loader2 className={cn('animate-spin text-[--blue]', sizes[size])} />
      {label && <span className="text-xs text-[--txt-3]">{label}</span>}
    </div>
  )
}
