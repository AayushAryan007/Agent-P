import { AlertTriangle, ArrowRight, CheckCircle2, Hand, ListTree, Plus } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { useMeta, useMetrics, useRuns } from '@/api/queries'
import { Button, EmptyState, ErrorState, Panel, Skeleton, StatTile } from '@/components/ui'
import { RunsTable } from '@/features/runs/RunsTable'
import { formatDuration, formatPercent, formatRelative, formatTokens } from '@/lib/format'

/** Every number here comes from GET /metrics/summary, derived server-side from stored runs (FR-26). */
function Kpis() {
  const m = useMetrics('7d')
  if (m.isError) {
    // Compact: the runs panel below already explains the error in full.
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {['Runs · 7d', 'Success rate', 'Avg duration', 'Tokens · 7d', 'Pending approvals'].map((l) => (
          <StatTile key={l} label={l} value="—" hint="unavailable" />
        ))}
      </div>
    )
  }
  const d = m.data
  const loading = m.isPending
  const terminal = d ? (d.runs_by_status.completed ?? 0) + (d.runs_by_status.failed ?? 0) + (d.runs_by_status.cancelled ?? 0) : 0
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <StatTile label="Runs · 7d" loading={loading} value={d?.runs_total ?? '—'} hint={d && `${d.runs_by_status.running ?? 0} running`} />
      <StatTile
        label="Success rate"
        loading={loading}
        value={formatPercent(d?.success_rate)}
        tone={d?.success_rate == null ? undefined : d.success_rate >= 0.8 ? 'green' : 'amber'}
        hint={d && (terminal ? `of ${terminal} finished runs` : 'no finished runs yet')}
      />
      <StatTile
        label="Avg duration"
        loading={loading}
        value={formatDuration(d?.avg_duration_ms)}
        hint={d?.p95_duration_ms != null ? `p95 ${formatDuration(d.p95_duration_ms)}` : undefined}
      />
      <StatTile label="Tokens · 7d" loading={loading} value={formatTokens(d?.total_tokens)} hint="input + output" />
      <StatTile
        label="Pending approvals"
        loading={loading}
        value={d?.pending_approvals ?? '—'}
        tone={d && d.pending_approvals > 0 ? 'amber' : undefined}
        hint={d && d.pending_approvals > 0 ? 'needs your review' : 'nothing waiting'}
      />
    </div>
  )
}

function Attention() {
  const m = useMetrics('7d')
  const failures = m.data?.recent_failures ?? []
  return (
    <Panel title="Needs attention" bodyClassName="p-0">
      {m.isPending ? (
        <div className="space-y-2 p-4">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : m.isError ? (
        <p className="p-4 text-fg-3">Unavailable while the backend is unreachable.</p>
      ) : failures.length === 0 && m.data.pending_approvals === 0 ? (
        <EmptyState icon={CheckCircle2} title="All clear">
          No failed runs or pending approvals in the last 7 days.
        </EmptyState>
      ) : (
        <ul className="divide-y divide-border/60">
          {m.data.pending_approvals > 0 && (
            <li>
              <Link to="/runs?status=waiting_approval" className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2">
                <Hand className="size-4 text-amber" aria-hidden />
                <span className="flex-1">
                  {m.data.pending_approvals} run{m.data.pending_approvals > 1 ? 's' : ''} awaiting patch approval
                </span>
                <ArrowRight className="size-4 text-fg-3" aria-hidden />
              </Link>
            </li>
          )}
          {failures.map((r) => (
            <li key={r.id}>
              <Link to={`/runs/${r.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2">
                <AlertTriangle className="size-4 shrink-0 text-red" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{r.task_title}</span>
                  <span className="block truncate font-mono text-[11px] text-fg-3">{r.status_reason ?? 'failed'}</span>
                </span>
                <span className="text-[12px] text-fg-3">{formatRelative(r.finished_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function Templates() {
  const meta = useMeta()
  const navigate = useNavigate()
  return (
    <Panel title="Workflow templates">
      {meta.isPending ? (
        <Skeleton className="h-20" />
      ) : meta.isError ? (
        <p className="text-fg-3">Templates load from the backend.</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {meta.data.templates.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => navigate(`/tasks/new?template=${t.key}`)}
              className="rounded-panel border border-border bg-surface-2 p-4 text-left transition-colors hover:border-border-strong"
            >
              <div className="font-medium">{t.title}</div>
              <p className="mt-1 text-fg-3">{t.description}</p>
              <p className="mt-2 font-mono text-[11px] text-fg-3">{t.steps.length} steps · {t.key}</p>
            </button>
          ))}
        </div>
      )}
    </Panel>
  )
}

export function DashboardPage() {
  const runs = useRuns(undefined, 8)
  const navigate = useNavigate()
  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6">
      <Kpis />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel
          title="Recent runs"
          bodyClassName="p-0"
          actions={
            <Link to="/runs" className="text-[12px] text-blue hover:underline">
              View all
            </Link>
          }
        >
          {runs.isPending ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }, (_, i) => (
                <Skeleton key={i} className="h-8" />
              ))}
            </div>
          ) : runs.isError ? (
            <ErrorState error={runs.error} onRetry={() => runs.refetch()} />
          ) : runs.data.items.length === 0 ? (
            <EmptyState
              icon={ListTree}
              title="No runs yet"
              action={
                <Button variant="primary" icon={Plus} onClick={() => navigate('/tasks/new')}>
                  Create your first task
                </Button>
              }
            >
              Start a task to watch agents inspect a repository, propose a fix, and verify it in a sandbox.
            </EmptyState>
          ) : (
            <RunsTable runs={runs.data.items} />
          )}
        </Panel>
        <Attention />
      </div>
      <Templates />
    </div>
  )
}
