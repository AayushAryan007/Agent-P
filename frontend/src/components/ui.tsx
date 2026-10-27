import clsx from 'clsx'
import { AlertTriangle, LoaderCircle, WifiOff, type LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { statusMeta, toneSoft, toneText, VERIFICATION, type Tone } from '@/domain/status'
import type { VerificationLabel } from '@/domain/events'

export function Panel({
  title,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={clsx('flex min-h-0 flex-col rounded-panel border border-border bg-surface-1', className)}>
      {(title || actions) && (
        <header className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-border px-4">
          {title && <h2 className="text-caps font-semibold uppercase text-fg-2">{title}</h2>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={clsx('min-h-0 flex-1', bodyClassName ?? 'p-4')}>{children}</div>
    </section>
  )
}

export function Badge({ tone, icon: Icon, children, spin }: { tone: Tone; icon?: LucideIcon; children: ReactNode; spin?: boolean }) {
  return (
    <span
      className={clsx(
        'inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-full px-2 text-[11px] font-medium ring-1 ring-inset',
        toneSoft[tone],
      )}
    >
      {Icon && <Icon aria-hidden className={clsx('size-3', spin && 'animate-spin')} />}
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const m = statusMeta(status)
  return (
    <Badge tone={m.tone} icon={m.icon} spin={m.spin}>
      {m.label}
    </Badge>
  )
}

export function VerificationBadge({ label }: { label: VerificationLabel | null }) {
  if (!label) return <span className="text-fg-3">—</span>
  const m = VERIFICATION[label]
  return (
    <Badge tone={m.tone} icon={m.icon}>
      {m.label}
    </Badge>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

const buttonVariants: Record<ButtonVariant, string> = {
  primary: 'bg-blue text-white hover:bg-blue/90 disabled:bg-blue/40',
  secondary: 'border border-border bg-surface-2 text-fg hover:bg-surface-3 hover:border-border-strong',
  ghost: 'text-fg-2 hover:bg-surface-3 hover:text-fg',
  danger: 'border border-red/40 bg-red/10 text-red hover:bg-red/20',
}

export function Button({
  variant = 'secondary',
  loading,
  icon: Icon,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; loading?: boolean; icon?: LucideIcon }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex h-8 items-center justify-center gap-1.5 rounded-control px-3 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60',
        buttonVariants[variant],
        className,
      )}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : Icon && <Icon className="size-4" aria-hidden />}
      {children}
    </button>
  )
}

export function StatTile({
  label,
  value,
  hint,
  tone,
  loading,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: Tone
  loading?: boolean
}) {
  return (
    <div className="rounded-panel border border-border bg-surface-1 px-4 py-3.5">
      <div className="text-caps font-semibold uppercase text-fg-3">{label}</div>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-24" />
      ) : (
        <div className={clsx('mt-1.5 font-mono text-[28px] leading-9 tabular-nums', tone ? toneText[tone] : 'text-fg')}>{value}</div>
      )}
      <div className="mt-0.5 h-4 text-[12px] text-fg-3">{hint}</div>
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={clsx('animate-pulse rounded-control bg-surface-3/70', className)} />
}

export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon: LucideIcon
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="mb-1 grid size-10 place-items-center rounded-full border border-border bg-surface-2">
        <Icon className="size-5 text-fg-3" aria-hidden />
      </div>
      <p className="text-sm font-medium text-fg">{title}</p>
      {children && <p className="max-w-sm text-fg-3">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiErr = error instanceof ApiError ? error : null
  const network = apiErr?.network ?? false
  return (
    <div role="alert" className="flex h-full flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="mb-1 grid size-10 place-items-center rounded-full border border-red/30 bg-red/10">
        {network ? <WifiOff className="size-5 text-red" aria-hidden /> : <AlertTriangle className="size-5 text-red" aria-hidden />}
      </div>
      <p className="text-sm font-medium text-fg">
        {network ? 'Backend unreachable' : (apiErr?.problem?.title ?? 'Something went wrong')}
      </p>
      <p className="max-w-md text-fg-3">{error instanceof Error ? error.message : String(error)}</p>
      {apiErr?.problem?.request_id && (
        <p className="font-mono text-[11px] text-fg-3">request_id {apiErr.problem.request_id}</p>
      )}
      {onRetry && (
        <Button className="mt-2" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}
