import { describe, expect, it } from 'vitest'
import { illustrativeEvents } from '@/fixtures/illustrativeRun'
import type { ExecutionEvent } from './events'
import { applyEvent, initialRunState, reduceEvents } from './runState'

const ev = (seq: number, event_type: string, extra: Partial<ExecutionEvent> = {}): ExecutionEvent => ({
  event_id: `e${seq}`,
  schema_version: 1,
  run_id: 'r1',
  sequence_number: seq,
  occurred_at: new Date(1_700_000_000_000 + seq * 1000).toISOString(),
  event_type,
  step_id: null,
  tool_invocation_id: null,
  parent_event_id: null,
  payload: {},
  ...extra,
})

const created = ev(1, 'workflow.created', {
  payload: {
    model: 'm',
    steps: [{ id: 's1', key: 'a', kind: 'agent', role: 'coordinator', title: 'A', depends_on: [] }],
  },
})

describe('applyEvent', () => {
  it('ignores duplicate and out-of-order sequence numbers (at-least-once delivery)', () => {
    const once = reduceEvents([created, ev(2, 'workflow.started'), ev(3, 'step.started', { step_id: 's1' })])
    const again = reduceEvents([ev(2, 'workflow.started'), ev(3, 'step.started', { step_id: 's1' })], once)
    expect(again).toBe(once)
    expect(again.events).toHaveLength(3)
  })

  it('tracks step lifecycle, retries and token totals', () => {
    const s = reduceEvents([
      created,
      ev(2, 'step.started', { step_id: 's1', payload: { attempt: 1 } }),
      ev(3, 'llm.call_completed', { step_id: 's1', payload: { input_tokens: 100, output_tokens: 20 } }),
      ev(4, 'step.started', { step_id: 's1', payload: { attempt: 2 } }),
      ev(5, 'step.completed', { step_id: 's1', payload: { output_summary: { ok: true } } }),
    ])
    expect(s.steps.s1).toMatchObject({ status: 'completed', attempt: 2, inputTokens: 100, outputTokens: 20, llmCalls: 1 })
    expect(s.totals.llmCalls).toBe(1)
  })

  it('records denied tool calls as invocations with a reason', () => {
    const s = reduceEvents([
      created,
      ev(2, 'tool.denied', { step_id: 's1', tool_invocation_id: 't1', payload: { tool_name: 'read_file', reason: 'policy:path' } }),
    ])
    expect(s.tools.t1).toMatchObject({ status: 'denied', error: 'policy:path' })
    expect(s.steps.s1?.toolInvocationIds).toEqual(['t1'])
  })

  it('keeps unknown event types in the timeline without changing state', () => {
    const base = reduceEvents([created])
    const s = applyEvent(base, ev(2, 'future.event_type'))
    expect(s.events).toHaveLength(2)
    expect(s.steps).toBe(base.steps)
  })

  it('reduces the illustrative fixture to a completed, verified run', () => {
    const s = reduceEvents(illustrativeEvents, initialRunState)
    expect(s.status).toBe('completed')
    expect(s.verificationLabel).toBe('verified')
    expect(Object.values(s.steps).every((st) => st.status === 'completed')).toBe(true)
  })
})
