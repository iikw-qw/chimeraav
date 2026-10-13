import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/cn'

const badge = cva(
  'inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md font-medium border',
  {
    variants: {
      variant: {
        success: 'bg-[--green]/10 text-[--green] border-[--green]/20',
        warning: 'bg-[--amber]/10 text-[--amber] border-[--amber]/20',
        danger: 'bg-[--red]/10 text-[--red] border-[--red]/20',
        info: 'bg-[--blue]/10 text-[--blue] border-[--blue]/20',
        neutral: 'bg-[--txt-2]/10 text-[--txt-2] border-[--txt-2]/20',
        purple: 'bg-[--purple]/10 text-[--purple] border-[--purple]/20',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badge> {}

export function Badge({ className, variant, ...rest }: BadgeProps) {
  return <span className={cn(badge({ variant }), className)} {...rest} />
}
