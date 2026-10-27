/**
 * Execution event schema v1 — mirrors docs/API_SPECIFICATION.md §5.
 * Payloads are typed loosely on purpose: the reducer reads only the fields it
 * needs and must tolerate unknown event types and extra fields.
 */

export type RunStatus =
  | 'queued'
  | 'running'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type StepStatus =
  | 'pending'
  | 'running'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'skipped'

export type ToolStatus = 'started' | 'completed' | 'failed' | 'denied'

export type VerificationLabel = 'verified' | 'partially_verified' | 'not_verified'

export type StepKind = 'agent' | 'system' | 'approval'

export type AgentRole = 'coordinator' | 'repo_analysis' | 'debugging' | 'verification' | 'review'

export interface StepDefinition {
  id: string
  key: string
  kind: StepKind
  role: AgentRole | null
  title: string
  depends_on: string[]
}

export interface ExecutionEvent {
  event_id: string
  schema_version: number
  run_id: string
  sequence_number: number
  occurred_at: string
  event_type: string
  step_id: string | null
  tool_invocation_id: string | null
  parent_event_id: string | null
  payload: Record<string, unknown>
}

/** Event families drive timeline coloring. */
export type EventFamily = 'workflow' | 'step' | 'llm' | 'tool' | 'approval' | 'sandbox' | 'narration' | 'other'

export function eventFamily(eventType: string): EventFamily {
  if (eventType === 'agent.message') return 'narration'
  const prefix = eventType.split('.')[0]
  switch (prefix) {
    case 'workflow':
    case 'step':
    case 'llm':
    case 'tool':
    case 'approval':
    case 'sandbox':
      return prefix
    case 'agent':
    case 'retry':
    case 'budget':
      return 'step'
    default:
      return 'other'
  }
}
