import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/cn'

const button = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--blue]/40',
  {
    variants: {
      variant: {
        primary:
          'bg-[--blue] text-white shadow-[0_2px_12px_rgba(91,155,255,0.3)] hover:shadow-[0_4px_20px_rgba(91,155,255,0.4)] hover:brightness-110 active:scale-[0.98]',
        secondary:
          'border border-[--blue]/40 text-[--blue] hover:bg-[--blue]/10 active:scale-[0.98]',
        ghost: 'text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]',
        danger:
          'bg-[--red]/10 text-[--red] hover:bg-[--red] hover:text-white active:scale-[0.98]',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4 text-sm',
        lg: 'h-11 px-5 text-base',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  loading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, loading, leftIcon, rightIcon, disabled, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(button({ variant, size }), className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  )
})
