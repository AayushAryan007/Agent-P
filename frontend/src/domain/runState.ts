import type {
  ExecutionEvent,
  RunStatus,
  StepDefinition,
  StepStatus,
  ToolStatus,
  VerificationLabel,
} from './events'

/**
 * Client-side projection of a run, built only from execution events.
 * The same reducer powers the live view and replay, so what you replay is
 * exactly what you would have seen live.
 */

export interface StepState extends StepDefinition {
  status: StepStatus
  attempt: number
  startedAt: string | null
  finishedAt: string | null
  inputTokens: number
  outputTokens: number
  llmCalls: number
  toolInvocationIds: string[]
  lastError: string | null
  outputSummary: unknown
}

export interface ToolState {
  id: string
  stepId: string | null
  toolName: string
  status: ToolStatus
  input: unknown
  outputSummary: unknown
  truncated: boolean
  error: string | null
  startedAt: string
  durationMs: number | null
}

export interface RunState {
  runId: string | null
  status: RunStatus
  verificationLabel: VerificationLabel | null
  statusReason: string | null
  model: string | null
  startedAt: string | null
  finishedAt: string | null
  lastSequence: number
  steps: Record<string, StepState>
  stepOrder: string[]
  tools: Record<string, ToolState>
  pendingApprovalId: string | null
  totals: { inputTokens: number; outputTokens: number; llmCalls: number; toolCalls: number }
  events: ExecutionEvent[]
}

export const initialRunState: RunState = {
  runId: null,
  status: 'queued',
  verificationLabel: null,
  statusReason: null,
  model: null,
  startedAt: null,
  finishedAt: null,
  lastSequence: 0,
  steps: {},
  stepOrder: [],
  tools: {},
  pendingApprovalId: null,
  totals: { inputTokens: 0, outputTokens: 0, llmCalls: 0, toolCalls: 0 },
  events: [],
}

const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0)

function updateStep(state: RunState, stepId: string | null, patch: (s: StepState) => Partial<StepState>): RunState {
  if (!stepId) return state
  const step = state.steps[stepId]
  if (!step) return state
  return { ...state, steps: { ...state.steps, [stepId]: { ...step, ...patch(step) } } }
}

/**
 * Apply one event. Events at or below `lastSequence` are ignored, which makes
 * at-least-once SSE delivery safe. Unknown event types are kept in `events`
 * (so the timeline shows them) but do not change derived state.
 */
export function applyEvent(prev: RunState, event: ExecutionEvent): RunState {
  if (event.sequence_number <= prev.lastSequence) return prev

  let state: RunState = {
    ...prev,
    runId: event.run_id,
    lastSequence: event.sequence_number,
    events: [...prev.events, event],
  }
  const p = event.payload
  const at = event.occurred_at

  switch (event.event_type) {
    case 'workflow.created': {
      const defs = Array.isArray(p.steps) ? (p.steps as StepDefinition[]) : []
      const steps: Record<string, StepState> = {}
      for (const d of defs) {
        steps[d.id] = {
          ...d,
          status: 'pending',
          attempt: 0,
          startedAt: null,
          finishedAt: null,
          inputTokens: 0,
          outputTokens: 0,
          llmCalls: 0,
          toolInvocationIds: [],
          lastError: null,
          outputSummary: null,
        }
      }
      return { ...state, status: 'queued', model: str(p.model), steps, stepOrder: defs.map((d) => d.id) }
    }
    case 'workflow.started':
      return { ...state, status: 'running', startedAt: at }
    case 'workflow.waiting_approval':
      return { ...state, status: 'waiting_approval', pendingApprovalId: str(p.approval_id) }
    case 'workflow.completed':
      return {
        ...state,
        status: 'completed',
        finishedAt: at,
        verificationLabel: (str(p.verification_label) as VerificationLabel | null) ?? null,
      }
    case 'workflow.failed':
      return { ...state, status: 'failed', finishedAt: at, statusReason: str(p.reason) }
    case 'workflow.cancelled':
      return { ...state, status: 'cancelled', finishedAt: at }

    case 'step.started':
      return updateStep(state, event.step_id, (s) => ({
        status: 'running',
        attempt: num(p.attempt) || s.attempt + 1,
        startedAt: s.startedAt ?? at,
        lastError: null,
      }))
    case 'step.status_changed': {
      const to = str(p.to) as StepStatus | null
      return to ? updateStep(state, event.step_id, () => ({ status: to })) : state
    }
    case 'step.completed':
      return updateStep(state, event.step_id, () => ({
        status: 'completed',
        finishedAt: at,
        outputSummary: p.output_summary ?? null,
      }))
    case 'step.failed':
      return updateStep(state, event.step_id, () => ({
        status: 'failed',
        finishedAt: at,
        lastError: str(p.message),
      }))
    case 'step.skipped':
      return updateStep(state, event.step_id, () => ({ status: 'skipped', finishedAt: at }))

    case 'llm.call_completed': {
      const inT = num(p.input_tokens)
      const outT = num(p.output_tokens)
      state = updateStep(state, event.step_id, (s) => ({
        inputTokens: s.inputTokens + inT,
        outputTokens: s.outputTokens + outT,
        llmCalls: s.llmCalls + 1,
      }))
      return {
        ...state,
        totals: {
          ...state.totals,
          inputTokens: state.totals.inputTokens + inT,
          outputTokens: state.totals.outputTokens + outT,
          llmCalls: state.totals.llmCalls + 1,
        },
      }
    }

    case 'tool.started':
    case 'tool.denied': {
      const id = event.tool_invocation_id
      if (!id) return state
      const denied = event.event_type === 'tool.denied'
      const tool: ToolState = {
        id,
        stepId: event.step_id,
        toolName: str(p.tool_name) ?? 'unknown',
        status: denied ? 'denied' : 'started',
        input: p.input ?? null,
        outputSummary: null,
        truncated: false,
        error: denied ? str(p.reason) : null,
        startedAt: at,
        durationMs: denied ? 0 : null,
      }
      state = updateStep(state, event.step_id, (s) => ({ toolInvocationIds: [...s.toolInvocationIds, id] }))
      return {
        ...state,
        tools: { ...state.tools, [id]: tool },
        totals: { ...state.totals, toolCalls: state.totals.toolCalls + 1 },
      }
    }
    case 'tool.completed':
    case 'tool.failed': {
      const id = event.tool_invocation_id
      const tool = id ? state.tools[id] : undefined
      if (!id || !tool) return state
      const failed = event.event_type === 'tool.failed'
      return {
        ...state,
        tools: {
          ...state.tools,
          [id]: {
            ...tool,
            status: failed ? 'failed' : 'completed',
            outputSummary: failed ? null : (p.output_summary ?? null),
            truncated: p.truncated === true,
            error: failed ? str(p.message) : null,
            durationMs: num(p.duration_ms),
          },
        },
      }
    }

    case 'approval.requested':
      return updateStep(state, event.step_id, () => ({ status: 'waiting_approval' }))
    case 'approval.resolved':
      return { ...state, pendingApprovalId: null, status: state.status === 'waiting_approval' ? 'running' : state.status }

    default:
      return state
  }
}

export function reduceEvents(events: readonly ExecutionEvent[], from: RunState = initialRunState): RunState {
  return events.reduce(applyEvent, from)
}

export const isTerminal = (s: RunStatus): boolean => s === 'completed' || s === 'failed' || s === 'cancelled'
