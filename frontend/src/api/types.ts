import type { ExecutionEvent, RunStatus, StepDefinition, StepStatus, VerificationLabel } from '@/domain/events'

/** Response shapes from docs/API_SPECIFICATION.md §3. */

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}

export interface Limits {
  max_minutes: number
  max_llm_calls: number
  max_total_tokens: number
  max_tool_calls: number
}

export type RepoSource = { kind: 'bundled'; key: string } | { kind: 'github'; url: string }

export interface RunTotals {
  llm_calls: number
  input_tokens: number
  output_tokens: number
  tool_calls: number
}

export interface RunListItem {
  id: string
  task_id: string
  task_title: string
  status: RunStatus
  status_reason: string | null
  verification_label: VerificationLabel | null
  queued_at: string
  started_at: string | null
  finished_at: string | null
  totals: RunTotals
}

export interface RunStep extends StepDefinition {
  status: StepStatus
  attempt: number
  started_at: string | null
  finished_at: string | null
}

export interface RunDetail extends RunListItem {
  model: string
  limits: Limits
  steps: RunStep[]
  last_sequence: number
}

export interface EventsPage {
  items: ExecutionEvent[]
  next_after_seq: number | null
}

export interface MetricsSummary {
  window: string
  runs_total: number
  runs_by_status: Partial<Record<RunStatus, number>>
  /** completed ÷ terminal runs; null when there are no terminal runs. */
  success_rate: number | null
  avg_duration_ms: number | null
  p95_duration_ms: number | null
  total_tokens: number
  pending_approvals: number
  recent_failures: RunListItem[]
}

export interface TemplateInfo {
  key: string
  title: string
  description: string
  steps: StepDefinition[]
  tools: { name: string; description: string; runs_in: 'api_worker' | 'sandbox' }[]
}

export interface BundledRepo {
  key: string
  title: string
  description: string
}

export interface ProviderInfo {
  name: string
  configured: boolean
  models: { id: string; role: 'default' | 'fallback' | 'available' }[]
}

export interface Meta {
  templates: TemplateInfo[]
  bundled_repos: BundledRepo[]
  providers: ProviderInfo[]
  limits_default: Limits
  limits_max: Limits
}

export interface Me {
  role: 'operator' | 'anonymous'
  csrf_token: string | null
}

export interface CreateTaskRequest {
  title: string
  goal: string
  template_key: string
  repo_source: RepoSource
  model: string
  limits: Limits
  visibility: 'public' | 'private'
}

export interface Task extends CreateTaskRequest {
  id: string
  created_at: string
}
