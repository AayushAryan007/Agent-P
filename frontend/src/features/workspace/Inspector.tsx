import * as Tabs from '@radix-ui/react-tabs'
import clsx from 'clsx'
import { MousePointerClick, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'
import { EmptyState, StatusBadge } from '@/components/ui'
import type { RunState, ToolState } from '@/domain/runState'
import { durationBetween, formatClock, formatDuration, formatTokens } from '@/lib/format'

const ROLE_LABEL: Record<string, string> = {
  coordinator: 'Coordinator agent',
  repo_analysis: 'Repository analysis agent',
  debugging: 'Debugging agent',
  verification: 'Test & verification agent',
  review: 'Review agent',
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="text-fg-3">{label}</dt>
      <dd className="text-right font-mono text-[12px] text-fg">{children}</dd>
    </div>
  )
}

function Json({ value }: { value: unknown }) {
  if (value == null) return <p className="text-fg-3">—</p>
  return (
    <pre className="max-h-72 overflow-auto rounded-control border border-border bg-bg p-3 font-mono text-[11.5px] leading-relaxed text-fg-2">
      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
    </pre>
  )
}

function ToolCard({ tool, active, onSelect }: { tool: ToolState; active: boolean; onSelect: () => void }) {
  return (
    <div className={clsx('rounded-control border', active ? 'border-cyan/60 bg-surface-2' : 'border-border')}>
      <button type="button" onClick={onSelect} className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left">
        <span className="flex items-center gap-2 font-mono text-[12px] text-cyan">
          <Wrench className="size-3.5" aria-hidden />
          {tool.toolName}
        </span>
        <span className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-fg-3">{formatDuration(tool.durationMs)}</span>
          <StatusBadge status={tool.status} />
        </span>
      </button>
      {active && (
        <div className="space-y-3 border-t border-border px-3 py-3">
          <div>
            <div className="mb-1 text-caps uppercase text-fg-3">Input (sanitized)</div>
            <Json value={tool.input} />
          </div>
          <div>
            <div className="mb-1 flex items-center gap-2 text-caps uppercase text-fg-3">
              Output summary {tool.truncated && <span className="normal-case tracking-normal text-amber">truncated</span>}
            </div>
            {tool.error ? <p className="text-red">{tool.error}</p> : <Json value={tool.outputSummary} />}
          </div>
          <dl className="border-t border-border pt-2">
            <Field label="Invocation">{tool.id.slice(0, 13)}…</Field>
            <Field label="Started">{formatClock(tool.startedAt)}</Field>
          </dl>
        </div>
      )}
    </div>
  )
}

const tabClass =
  'h-9 border-b-2 border-transparent px-1 text-[12px] font-medium text-fg-3 hover:text-fg data-[state=active]:border-blue data-[state=active]:text-fg'

export function Inspector({
  state,
  stepId,
  toolId,
  onSelectTool,
  now,
}: {
  state: RunState
  stepId: string | null
  toolId: string | null
  onSelectTool: (id: string | null) => void
  now: number
}) {
  const step = stepId ? state.steps[stepId] : undefined
  if (!step) {
    return (
      <EmptyState icon={MousePointerClick} title="Select a step">
        Click a node in the graph or an event in the timeline to inspect its inputs, tool calls and output.
      </EmptyState>
    )
  }
  const tools = step.toolInvocationIds.map((id) => state.tools[id]).filter((t): t is ToolState => !!t)

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 pb-3 pt-4">
        <div className="text-caps uppercase text-fg-3">
          {step.role ? ROLE_LABEL[step.role] : step.kind === 'approval' ? 'Human approval gate' : 'System step (deterministic)'}
        </div>
        <div className="mt-1 flex items-center justify-between gap-3">
          <h3 className="truncate text-[16px] font-semibold">{step.title}</h3>
          <StatusBadge status={step.status} />
        </div>
      </div>

      <Tabs.Root defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
        <Tabs.List className="flex gap-5 border-b border-border px-4" aria-label="Step details">
          <Tabs.Trigger value="overview" className={tabClass}>
            Overview
          </Tabs.Trigger>
          <Tabs.Trigger value="tools" className={tabClass}>
            Tool calls <span className="ml-1 text-fg-3">{tools.length}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="output" className={tabClass}>
            Output
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="overview" className="min-h-0 flex-1 overflow-auto px-4 py-3">
          <dl className="divide-y divide-border/60">
            <Field label="Key">{step.key}</Field>
            <Field label="Attempt">{step.attempt || '—'}</Field>
            <Field label="Started">{step.startedAt ? formatClock(step.startedAt) : '—'}</Field>
            <Field label="Finished">{step.finishedAt ? formatClock(step.finishedAt) : '—'}</Field>
            <Field label="Duration">{formatDuration(durationBetween(step.startedAt, step.finishedAt, now))}</Field>
            <Field label="LLM calls">{step.llmCalls}</Field>
            <Field label="Tokens in / out">
              {formatTokens(step.inputTokens)} / {formatTokens(step.outputTokens)}
            </Field>
            <Field label="Depends on">{step.depends_on.join(', ') || '—'}</Field>
          </dl>
          {step.lastError && (
            <div className="mt-4 rounded-control border border-red/30 bg-red/10 p-3 text-red">{step.lastError}</div>
          )}
        </Tabs.Content>

        <Tabs.Content value="tools" className="min-h-0 flex-1 space-y-2 overflow-auto px-4 py-3">
          {tools.length === 0 ? (
            <p className="text-fg-3">No tool calls for this step.</p>
          ) : (
            tools.map((t) => (
              <ToolCard key={t.id} tool={t} active={t.id === toolId} onSelect={() => onSelectTool(t.id === toolId ? null : t.id)} />
            ))
          )}
        </Tabs.Content>

        <Tabs.Content value="output" className="min-h-0 flex-1 overflow-auto px-4 py-3">
          <Json value={step.outputSummary} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}
