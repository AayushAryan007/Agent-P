import {
  Ban,
  CheckCircle2,
  Circle,
  CircleDashed,
  Hand,
  LoaderCircle,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  SkipForward,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import type { RunStatus, StepStatus, ToolStatus, VerificationLabel } from './events'

/** Single source of truth for status → color/icon/label (docs/DESIGN_SYSTEM.md §2). */

export type Tone = 'blue' | 'violet' | 'cyan' | 'green' | 'amber' | 'red' | 'slate'

export interface StatusMeta {
  label: string
  tone: Tone
  icon: LucideIcon
  spin?: boolean
}

type AnyStatus = RunStatus | StepStatus | ToolStatus

const STATUS: Record<AnyStatus, StatusMeta> = {
  queued: { label: 'Queued', tone: 'slate', icon: CircleDashed },
  pending: { label: 'Pending', tone: 'slate', icon: CircleDashed },
  running: { label: 'Running', tone: 'blue', icon: LoaderCircle, spin: true },
  started: { label: 'Running', tone: 'blue', icon: LoaderCircle, spin: true },
  waiting_approval: { label: 'Awaiting approval', tone: 'amber', icon: Hand },
  completed: { label: 'Completed', tone: 'green', icon: CheckCircle2 },
  failed: { label: 'Failed', tone: 'red', icon: XCircle },
  denied: { label: 'Denied', tone: 'red', icon: Ban },
  cancelled: { label: 'Cancelled', tone: 'slate', icon: Ban },
  skipped: { label: 'Skipped', tone: 'slate', icon: SkipForward },
}

export function statusMeta(status: string): StatusMeta {
  return STATUS[status as AnyStatus] ?? { label: status, tone: 'slate', icon: Circle }
}

export const VERIFICATION: Record<VerificationLabel, StatusMeta> = {
  verified: { label: 'Verified', tone: 'green', icon: ShieldCheck },
  partially_verified: { label: 'Partially verified', tone: 'amber', icon: ShieldAlert },
  not_verified: { label: 'Not verified', tone: 'red', icon: ShieldX },
}

/** Static class maps so Tailwind can see every class at build time. */
export const toneText: Record<Tone, string> = {
  blue: 'text-blue',
  violet: 'text-violet',
  cyan: 'text-cyan',
  green: 'text-green',
  amber: 'text-amber',
  red: 'text-red',
  slate: 'text-slate',
}

export const toneSoft: Record<Tone, string> = {
  blue: 'bg-blue/12 text-blue ring-blue/30',
  violet: 'bg-violet/12 text-violet ring-violet/30',
  cyan: 'bg-cyan/12 text-cyan ring-cyan/30',
  green: 'bg-green/12 text-green ring-green/30',
  amber: 'bg-amber/12 text-amber ring-amber/30',
  red: 'bg-red/12 text-red ring-red/30',
  slate: 'bg-slate/12 text-fg-2 ring-slate/30',
}

export const toneBorder: Record<Tone, string> = {
  blue: 'border-blue',
  violet: 'border-violet',
  cyan: 'border-cyan',
  green: 'border-green',
  amber: 'border-amber',
  red: 'border-red',
  slate: 'border-border-strong',
}

export const toneStroke: Record<Tone, string> = {
  blue: 'var(--color-blue)',
  violet: 'var(--color-violet)',
  cyan: 'var(--color-cyan)',
  green: 'var(--color-green)',
  amber: 'var(--color-amber)',
  red: 'var(--color-red)',
  slate: 'var(--color-border-strong)',
}
