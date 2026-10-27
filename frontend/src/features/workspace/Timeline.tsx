import clsx from 'clsx'
import { useEffect, useRef } from 'react'
import { eventFamily, type EventFamily, type ExecutionEvent } from '@/domain/events'
import type { RunState } from '@/domain/runState'
import { formatClock } from '@/lib/format'
import { describeEvent } from './describeEvent'

const FAMILY_STYLE: Record<EventFamily, string> = {
  workflow: 'text-blue',
  step: 'text-fg-2',
  llm: 'text-violet',
  tool: 'text-cyan',
  approval: 'text-amber',
  sandbox: 'text-cyan',
  narration: 'text-violet',
  other: 'text-fg-3',
}

function rowTone(e: ExecutionEvent): string | null {
  if (e.event_type.endsWith('.failed') || e.event_type === 'tool.denied' || e.event_type === 'agent.output_invalid')
    return 'text-red'
  if (e.event_type === 'retry.scheduled' || e.event_type === 'llm.rate_limited' || e.event_type === 'budget.warning')
    return 'text-amber'
  return null
}

/**
 * Ordered event log. Follows the tail while the user is at the bottom.
 * TODO(M3): virtualize with TanStack Virtual once runs exceed ~500 events (NFR-7).
 */
export function Timeline({
  state,
  selectedStepId,
  onSelect,
}: {
  state: RunState
  selectedStepId: string | null
  onSelect: (stepId: string | null, toolId: string | null) => void
}) {
  const scroller = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)

  useEffect(() => {
    const el = scroller.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [state.events.length])

  return (
    <div
      ref={scroller}
      onScroll={(e) => {
        const el = e.currentTarget
        pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
      }}
      className="h-full overflow-auto font-mono text-[12px]"
      role="log"
      aria-label="Execution events"
    >
      {state.events.length === 0 && <p className="p-4 font-sans text-fg-3">No events yet.</p>}
      <ol>
        {state.events.map((e) => {
          const family = eventFamily(e.event_type)
          const narration = family === 'narration'
          return (
            <li key={e.event_id}>
              <button
                type="button"
                onClick={() => onSelect(e.step_id, e.tool_invocation_id)}
                className={clsx(
                  'grid w-full grid-cols-[3.5rem_6.5rem_9.5rem_1fr] items-baseline gap-3 px-4 py-1 text-left hover:bg-surface-3',
                  e.step_id && e.step_id === selectedStepId && 'bg-surface-2',
                )}
              >
                <span className="text-right tabular-nums text-fg-3">#{e.sequence_number}</span>
                <span className="tabular-nums text-fg-3">{formatClock(e.occurred_at)}</span>
                <span className={clsx('truncate', FAMILY_STYLE[family])}>{e.event_type}</span>
                <span
                  className={clsx(
                    'truncate',
                    narration ? 'border-l-2 border-violet/50 pl-2 font-sans italic text-fg-2' : (rowTone(e) ?? 'text-fg'),
                  )}
                  title={narration ? 'Model narration — not a recorded fact' : undefined}
                >
                  {describeEvent(e, state)}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
