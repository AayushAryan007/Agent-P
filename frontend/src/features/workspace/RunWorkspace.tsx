import clsx from 'clsx'
import { Clock, Coins, Wrench } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { StatusBadge, VerificationBadge } from '@/components/ui'
import { isTerminal, type RunState } from '@/domain/runState'
import { statusMeta, toneText } from '@/domain/status'
import { durationBetween, formatDuration, formatTokens } from '@/lib/format'
import { AgentGraph } from './AgentGraph'
import { Inspector } from './Inspector'
import { Timeline } from './Timeline'

/** Ticks once a second while the run is active so elapsed timers advance between events. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [active])
  return now
}

/**
 * The live execution workspace layout (docs/DESIGN_SYSTEM.md §4). Purely a
 * function of RunState, so live streaming and replay render identically.
 */
export function RunWorkspace({
  title,
  state,
  banner,
  toolbar,
  nowOverride,
  initialStepId = null,
}: {
  title: string
  state: RunState
  banner?: ReactNode
  toolbar?: ReactNode
  /** Replay supplies its own clock so timers reflect recorded time, not wall time. */
  nowOverride?: number
  initialStepId?: string | null
}) {
  const liveNow = useNow(!isTerminal(state.status) && nowOverride == null)
  const now = nowOverride ?? liveNow
  const [stepId, setStepId] = useState<string | null>(initialStepId)
  const [toolId, setToolId] = useState<string | null>(null)

  const elapsed = durationBetween(state.startedAt, state.finishedAt, now)
  const tokens = state.totals.inputTokens + state.totals.outputTokens

  return (
    <div className="flex h-full min-h-[640px] flex-col">
      {banner}
      <div className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border px-6">
        <div className="flex min-w-0 items-center gap-3">
          <h1 className="truncate text-[15px] font-semibold">{title}</h1>
          <StatusBadge status={state.status} />
          <VerificationBadge label={state.verificationLabel} />
        </div>
        <div className="flex items-center gap-5 text-[12px] text-fg-2">
          <span className="flex items-center gap-1.5 font-mono" title="Elapsed">
            <Clock className="size-3.5 text-fg-3" aria-hidden />
            {formatDuration(elapsed)}
          </span>
          <span className="flex items-center gap-1.5 font-mono" title="Tokens (in + out)">
            <Coins className="size-3.5 text-fg-3" aria-hidden />
            {formatTokens(tokens)}
          </span>
          <span className="flex items-center gap-1.5 font-mono" title="Tool calls">
            <Wrench className="size-3.5 text-fg-3" aria-hidden />
            {state.totals.toolCalls}
          </span>
          {state.model && <span className="font-mono text-fg-3">{state.model}</span>}
          {toolbar}
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[240px_minmax(0,1fr)_380px]">
        <aside className="min-h-0 overflow-auto border-r border-border bg-surface-1" aria-label="Steps">
          <div className="px-4 pb-2 pt-4 text-caps font-semibold uppercase text-fg-3">Workflow steps</div>
          <ol className="px-2 pb-4">
            {state.stepOrder.map((id, i) => {
              const s = state.steps[id]
              if (!s) return null
              const m = statusMeta(s.status)
              const Icon = m.icon
              return (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => {
                      setStepId(id)
                      setToolId(null)
                    }}
                    className={clsx(
                      'flex w-full items-center gap-2.5 rounded-control px-2 py-2 text-left hover:bg-surface-3',
                      id === stepId && 'bg-surface-3',
                    )}
                  >
                    <span className="w-4 text-right font-mono text-[11px] text-fg-3">{i + 1}</span>
                    <Icon className={clsx('size-4 shrink-0', toneText[m.tone], m.spin && 'animate-spin')} aria-label={m.label} />
                    <span className="min-w-0 flex-1 truncate">{s.title}</span>
                    <span className="font-mono text-[11px] text-fg-3">
                      {formatDuration(durationBetween(s.startedAt, s.finishedAt, now)).replace('—', '')}
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        </aside>

        <div className="grid min-h-0 grid-rows-[minmax(0,1fr)_260px]">
          <div className="min-h-0 bg-bg">
            <AgentGraph
              state={state}
              selectedStepId={stepId}
              onSelectStep={(id) => {
                setStepId(id)
                setToolId(null)
              }}
              now={now}
            />
          </div>
          <div className="flex min-h-0 flex-col border-t border-border bg-surface-1">
            <div className="flex h-9 shrink-0 items-center justify-between px-4">
              <span className="text-caps font-semibold uppercase text-fg-3">Event timeline</span>
              <span className="font-mono text-[11px] text-fg-3">{state.events.length} events · seq {state.lastSequence}</span>
            </div>
            <div className="min-h-0 flex-1">
              <Timeline
                state={state}
                selectedStepId={stepId}
                onSelect={(s, t) => {
                  if (s) setStepId(s)
                  setToolId(t)
                }}
              />
            </div>
          </div>
        </div>

        <aside className="min-h-0 border-l border-border bg-surface-1" aria-label="Inspector">
          <Inspector state={state} stepId={stepId} toolId={toolId} onSelectTool={setToolId} now={now} />
        </aside>
      </div>
    </div>
  )
}
