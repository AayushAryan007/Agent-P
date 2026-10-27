import type { ExecutionEvent, StepDefinition } from '@/domain/events'

/**
 * ILLUSTRATIVE FIXTURE — hand-written events for design work on /dev/preview.
 * Not produced by the backend and never shown outside dev builds.
 * Shapes follow docs/API_SPECIFICATION.md §5 so the real reducer consumes them.
 */

const RUN = 'fixture-run'
const steps: StepDefinition[] = [
  { id: 's-prep', key: 'prepare_workspace', kind: 'system', role: null, title: 'Prepare workspace', depends_on: [] },
  { id: 's-plan', key: 'plan', kind: 'agent', role: 'coordinator', title: 'Coordinator · plan', depends_on: ['prepare_workspace'] },
  { id: 's-base', key: 'baseline', kind: 'system', role: null, title: 'Baseline tests + bench', depends_on: ['prepare_workspace'] },
  { id: 's-anl', key: 'analyze', kind: 'agent', role: 'repo_analysis', title: 'Repository analysis', depends_on: ['plan'] },
  { id: 's-dbg', key: 'debug', kind: 'agent', role: 'debugging', title: 'Debugging · patch', depends_on: ['analyze'] },
  { id: 's-apr', key: 'approve_patch', kind: 'approval', role: null, title: 'Approve patch', depends_on: ['debug'] },
  { id: 's-ver', key: 'verify', kind: 'agent', role: 'verification', title: 'Test & verification', depends_on: ['approve_patch', 'baseline'] },
  { id: 's-rev', key: 'review', kind: 'agent', role: 'review', title: 'Review', depends_on: ['verify'] },
  { id: 's-rep', key: 'report', kind: 'agent', role: 'coordinator', title: 'Coordinator · report', depends_on: ['review'] },
]

type Spec = [ms: number, type: string, step: string | null, tool: string | null, payload: Record<string, unknown>]

const t0 = Date.parse('2026-10-27T17:30:00.000Z')
const specs: Spec[] = [
  [0, 'workflow.created', null, null, { steps, model: 'gemini-3.8-flash', template_key: 'slow-endpoint-v1' }],
  [300, 'workflow.started', null, null, { worker_id: 'worker-1' }],
  [400, 'step.started', 's-prep', null, { attempt: 1 }],
  [500, 'sandbox.started', 's-prep', null, { purpose: 'clone', image: 'agentp-sandbox-python' }],
  [2100, 'sandbox.finished', 's-prep', null, { purpose: 'clone', exit_code: 0, duration_ms: 1600 }],
  [2200, 'step.completed', 's-prep', null, { duration_ms: 1800, output_summary: { files: 42, python_files: 18 } }],
  [2300, 'step.started', 's-plan', null, { attempt: 1 }],
  [2300, 'step.started', 's-base', null, { attempt: 1 }],
  [2350, 'sandbox.started', 's-base', null, { purpose: 'test' }],
  [2400, 'llm.call_started', 's-plan', null, { model: 'gemini-3.8-flash' }],
  [5200, 'llm.call_completed', 's-plan', null, { input_tokens: 3120, output_tokens: 610, latency_ms: 2800 }],
  [5250, 'agent.message', 's-plan', null, { kind: 'narration', text: 'Plan: locate the /orders handler, inspect ORM access patterns, then measure.' }],
  [5300, 'step.completed', 's-plan', null, { duration_ms: 3000, output_summary: { subtasks: 4 } }],
  [5400, 'step.started', 's-anl', null, { attempt: 1 }],
  [5500, 'tool.started', 's-anl', 't1', { tool_name: 'list_tree', input: { path: '.', depth: 3 } }],
  [5560, 'tool.completed', 's-anl', 't1', { duration_ms: 60, output_summary: { entries: 42 } }],
  [5600, 'tool.started', 's-anl', 't2', { tool_name: 'search_code', input: { query: '@router.get("/orders"' } }],
  [5690, 'tool.completed', 's-anl', 't2', { duration_ms: 90, output_summary: { hits: [{ path: 'app/api/orders.py', line: 14 }] } }],
  [5700, 'tool.started', 's-anl', 't3', { tool_name: 'read_file', input: { path: 'app/api/orders.py' } }],
  [5740, 'tool.completed', 's-anl', 't3', { duration_ms: 40, output_summary: { lines: 88 } }],
  [5800, 'tool.denied', 's-anl', 't4', { tool_name: 'read_file', reason: 'policy:path (../.env outside repository)' }],
  [6800, 'sandbox.finished', 's-base', null, { purpose: 'test', exit_code: 0, duration_ms: 4450 }],
  [6900, 'step.completed', 's-base', null, { duration_ms: 4600, output_summary: { tests_passed: 23, bench_p50_ms: 812 } }],
  [7000, 'llm.call_started', 's-anl', null, { model: 'gemini-3.8-flash' }],
  [9800, 'llm.call_completed', 's-anl', null, { input_tokens: 9400, output_tokens: 920, latency_ms: 2800 }],
  [9900, 'step.completed', 's-anl', null, { duration_ms: 4500, output_summary: { suspect: 'N+1 query in list_orders()' } }],
  [10000, 'step.started', 's-dbg', null, { attempt: 1 }],
  [10100, 'llm.call_started', 's-dbg', null, { model: 'gemini-3.8-flash' }],
  [13300, 'llm.call_completed', 's-dbg', null, { input_tokens: 11200, output_tokens: 1400, latency_ms: 3200 }],
  [13350, 'agent.output_invalid', 's-dbg', null, { attempt: 1, validation_errors: ['edits[0].search: field required'] }],
  [13400, 'retry.scheduled', 's-dbg', null, { target: 'llm_call', attempt: 2, delay_ms: 0, reason: 'invalid_output' }],
  [13500, 'llm.call_started', 's-dbg', null, { model: 'gemini-3.8-flash' }],
  [16000, 'llm.call_completed', 's-dbg', null, { input_tokens: 12100, output_tokens: 1250, latency_ms: 2500 }],
  [16100, 'tool.started', 's-dbg', 't5', { tool_name: 'propose_patch', input: { files: ['app/api/orders.py'] } }],
  [16900, 'tool.completed', 's-dbg', 't5', { duration_ms: 800, output_summary: { applies_cleanly: true, additions: 3, deletions: 5 } }],
  [17000, 'step.completed', 's-dbg', null, { duration_ms: 7000, output_summary: { root_cause: 'Lazy-loaded order.items per row', fix: 'selectinload(Order.items)' } }],
  [17100, 'step.started', 's-apr', null, { attempt: 1 }],
  [17150, 'approval.requested', 's-apr', null, { approval_id: 'a1', kind: 'apply_patch', summary: 'Eager-load items in list_orders()' }],
  [17200, 'workflow.waiting_approval', null, null, { approval_id: 'a1' }],
  [29000, 'approval.resolved', 's-apr', null, { approval_id: 'a1', decision: 'approved', actor: 'admin' }],
  [29050, 'step.completed', 's-apr', null, { duration_ms: 11950 }],
  [29100, 'step.started', 's-ver', null, { attempt: 1 }],
  [29200, 'sandbox.started', 's-ver', null, { purpose: 'test' }],
  [33400, 'sandbox.finished', 's-ver', null, { purpose: 'test', exit_code: 0, duration_ms: 4200 }],
  [33500, 'sandbox.started', 's-ver', null, { purpose: 'bench' }],
  [36600, 'sandbox.finished', 's-ver', null, { purpose: 'bench', exit_code: 0, duration_ms: 3100 }],
  [36700, 'step.completed', 's-ver', null, { duration_ms: 7600, output_summary: { tests_passed: 23, bench_p50_ms: { before: 812, after: 64 } } }],
  [36800, 'step.started', 's-rev', null, { attempt: 1 }],
  [36900, 'llm.call_started', 's-rev', null, { model: 'gemini-3.8-flash' }],
  [39400, 'llm.call_completed', 's-rev', null, { input_tokens: 6200, output_tokens: 540, latency_ms: 2500 }],
  [39500, 'step.completed', 's-rev', null, { duration_ms: 2700, output_summary: { findings: 0, touches_tests: false } }],
  [39600, 'step.started', 's-rep', null, { attempt: 1 }],
  [39700, 'llm.call_started', 's-rep', null, { model: 'gemini-3.8-flash' }],
  [41900, 'llm.call_completed', 's-rep', null, { input_tokens: 4800, output_tokens: 880, latency_ms: 2200 }],
  [42000, 'artifact.created', 's-rep', null, { kind: 'report', name: 'report.md', size_bytes: 4210 }],
  [42050, 'step.completed', 's-rep', null, { duration_ms: 2450 }],
  [42100, 'workflow.completed', null, null, { verification_label: 'verified' }],
]

export const illustrativeEvents: ExecutionEvent[] = specs.map(([ms, type, step, tool, payload], i) => ({
  event_id: `fx-${i + 1}`,
  schema_version: 1,
  run_id: RUN,
  sequence_number: i + 1,
  occurred_at: new Date(t0 + ms).toISOString(),
  event_type: type,
  step_id: step,
  tool_invocation_id: tool,
  parent_event_id: null,
  payload,
}))
