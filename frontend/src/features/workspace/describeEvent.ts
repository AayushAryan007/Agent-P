import type { ExecutionEvent } from '@/domain/events'
import type { RunState } from '@/domain/runState'
import { formatDuration, formatTokens } from '@/lib/format'

const s = (v: unknown): string => (typeof v === 'string' ? v : v == null ? '' : JSON.stringify(v))

/** One-line, human-readable summary of an event for the timeline. Unknown types fall back to the raw type. */
export function describeEvent(e: ExecutionEvent, state: RunState): string {
  const p = e.payload
  const step = e.step_id ? state.steps[e.step_id]?.title : undefined
  const tool = e.tool_invocation_id ? state.tools[e.tool_invocation_id]?.toolName : undefined

  switch (e.event_type) {
    case 'workflow.created':
      return `Workflow created · ${Array.isArray(p.steps) ? p.steps.length : 0} steps · ${s(p.model)}`
    case 'workflow.started':
      return 'Workflow started'
    case 'workflow.waiting_approval':
      return 'Waiting for human approval'
    case 'workflow.completed':
      return `Workflow completed · ${s(p.verification_label).replaceAll('_', ' ')}`
    case 'workflow.failed':
      return `Workflow failed · ${s(p.reason)}`
    case 'workflow.cancelled':
      return 'Workflow cancelled'
    case 'step.started':
      return `${step} started${typeof p.attempt === 'number' && p.attempt > 1 ? ` (attempt ${p.attempt})` : ''}`
    case 'step.completed':
      return `${step} completed in ${formatDuration(p.duration_ms as number)}`
    case 'step.failed':
      return `${step} failed: ${s(p.message)}`
    case 'step.skipped':
      return `${step} skipped: ${s(p.reason)}`
    case 'llm.call_started':
      return `${step} → ${s(p.model)}`
    case 'llm.call_completed':
      return `${step} ← ${formatTokens(p.input_tokens as number)} in / ${formatTokens(p.output_tokens as number)} out · ${formatDuration(p.latency_ms as number)}`
    case 'llm.rate_limited':
      return `Rate limited · retry in ${formatDuration(p.retry_after_ms as number)}`
    case 'agent.output_invalid':
      return `${step} returned invalid output (${Array.isArray(p.validation_errors) ? p.validation_errors.length : 0} errors)`
    case 'agent.message':
      return s(p.text)
    case 'tool.started':
      return `${tool}(${summarizeArgs(p.input)})`
    case 'tool.completed':
      return `${tool} ✓ ${formatDuration(p.duration_ms as number)}${p.truncated ? ' · truncated' : ''}`
    case 'tool.failed':
      return `${tool} ✗ ${s(p.message)}`
    case 'tool.denied':
      return `${s(p.tool_name)} denied: ${s(p.reason)}`
    case 'retry.scheduled':
      return `Retry ${s(p.target)} #${s(p.attempt)} in ${formatDuration(p.delay_ms as number)} · ${s(p.reason)}`
    case 'approval.requested':
      return `Approval requested: ${s(p.summary)}`
    case 'approval.resolved':
      return `Approval ${s(p.decision)} by ${s(p.actor)}${p.comment ? ` — “${s(p.comment)}”` : ''}`
    case 'sandbox.started':
      return `Sandbox ${s(p.purpose)} started`
    case 'sandbox.finished':
      return `Sandbox ${s(p.purpose)} exited ${s(p.exit_code)} in ${formatDuration(p.duration_ms as number)}${p.timed_out ? ' · timed out' : ''}`
    case 'artifact.created':
      return `Artifact ${s(p.kind)}: ${s(p.name)}`
    case 'budget.warning':
      return `Budget ${s(p.budget)} at ${s(p.used)}/${s(p.limit)}`
    default:
      return e.event_type
  }
}

function summarizeArgs(input: unknown): string {
  if (!input || typeof input !== 'object') return ''
  return Object.entries(input as Record<string, unknown>)
    .slice(0, 2)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? JSON.stringify(v.length > 40 ? v.slice(0, 40) + '…' : v) : JSON.stringify(v)}`)
    .join(', ')
}
