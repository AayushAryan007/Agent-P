import { ArrowLeft, Bot, Database, FileText } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { useArtifact, useRun, useRunArtifacts } from '@/api/queries'
import { DiffView } from '@/components/DiffView'
import { EmptyState, ErrorState, Panel, Skeleton, VerificationBadge } from '@/components/ui'
import type { VerificationLabel } from '@/domain/events'

/* Shapes written by the backend report step (app/orchestrator/steps.py: report). */
interface TestsJson {
  ran: boolean
  collected: number
  passed: number
  failed: number
  errors: number
  skipped: number
  failing_tests: string[]
  note: string | null
}
interface BenchJson {
  ran: boolean
  name: string | null
  unit: string | null
  p50: number | null
  p95: number | null
  note: string | null
}
interface ReportJson {
  verification_label: VerificationLabel
  verification_reasons: string[]
  narrative: { problem_summary: string; root_cause: string; fix_summary: string; limitations: string[]; next_steps: string[] }
  recorded: {
    verify?: {
      tests_before?: TestsJson
      tests_after?: TestsJson
      bench_before?: BenchJson | null
      bench_after?: BenchJson | null
      improvement?: number | null
      touched_protected?: string[]
    } | null
    approval?: { decision: string; comment: string | null } | null
  }
  patch_artifact_id: string | null
  review: { assessment: string; concerns: string[]; behaviour_preserved: boolean; recommendation: string } | null
}

function SourceTag({ kind }: { kind: 'model' | 'recorded' }) {
  return kind === 'model' ? (
    <span className="inline-flex items-center gap-1 rounded-full border border-violet/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-violet">
      <Bot className="size-3" aria-hidden /> Model-written
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full border border-cyan/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-cyan">
      <Database className="size-3" aria-hidden /> Recorded
    </span>
  )
}

function Section({ title, source, children }: { title: string; source: 'model' | 'recorded'; children: ReactNode }) {
  return (
    <Panel title={title} actions={<SourceTag kind={source} />}>
      {children}
    </Panel>
  )
}

function testsLine(t?: TestsJson): string {
  if (!t) return '—'
  if (!t.ran) return `did not run${t.note ? ` (${t.note})` : ''}`
  return `${t.passed} passed · ${t.failed} failed · ${t.errors} errors · ${t.skipped} skipped (of ${t.collected})`
}

function benchValue(b?: BenchJson | null): string {
  if (!b) return '—'
  if (!b.ran || b.p50 == null) return `not measured${b.note ? ` (${b.note})` : ''}`
  return `${b.p50} ${b.unit ?? ''} p50`
}

function Patch({ id }: { id: string }) {
  const patch = useArtifact(id)
  if (patch.isPending) return <Skeleton className="h-40" />
  if (patch.isError) return <ErrorState error={patch.error} />
  return <DiffView diff={patch.data.text ?? ''} maxHeight={520} />
}

export function ReportPage() {
  const { runId = '' } = useParams()
  const run = useRun(runId)
  const artifacts = useRunArtifacts(runId)
  const reportMeta = artifacts.data?.filter((a) => a.kind === 'report').at(-1)
  const report = useArtifact(reportMeta?.id ?? null)

  if (run.isError) return <ErrorState error={run.error} onRetry={() => run.refetch()} />
  if (artifacts.isError) return <ErrorState error={artifacts.error} onRetry={() => artifacts.refetch()} />
  if (run.isPending || artifacts.isPending || (reportMeta && report.isPending)) return <Skeleton className="m-6 h-[600px]" />
  if (!reportMeta) {
    return (
      <EmptyState icon={FileText} title="No report yet" action={<Link className="text-blue hover:underline" to={`/runs/${runId}`}>Back to run</Link>}>
        The report is written by the final step of a run.
      </EmptyState>
    )
  }
  if (report.isError) return <ErrorState error={report.error} onRetry={() => report.refetch()} />
  const r = report.data?.data as unknown as ReportJson
  const v = r.recorded.verify ?? null
  const evidence = (artifacts.data ?? []).filter((a) => a.kind !== 'report')

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-6">
      <Link to={`/runs/${runId}`} className="inline-flex items-center gap-1.5 text-[12px] text-fg-3 hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Back to run
      </Link>

      <header className="rounded-panel border border-border bg-surface-1 p-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-[22px] font-semibold">{run.data.task_title}</h1>
          <VerificationBadge label={r.verification_label} />
          <SourceTag kind="recorded" />
        </div>
        <ul className="mt-3 space-y-1 text-fg-2">
          {r.verification_reasons.map((x) => (
            <li key={x}>• {x}</li>
          ))}
        </ul>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section title="Problem" source="model">
          <p className="whitespace-pre-wrap leading-relaxed text-fg-2">{r.narrative.problem_summary}</p>
        </Section>
        <Section title="Root cause" source="model">
          <p className="whitespace-pre-wrap leading-relaxed text-fg-2">{r.narrative.root_cause}</p>
        </Section>
        <Section title="Fix" source="model">
          <p className="whitespace-pre-wrap leading-relaxed text-fg-2">{r.narrative.fix_summary}</p>
        </Section>
      </div>

      <Section title="Verification results" source="recorded">
        {v ? (
          <table className="w-full text-left">
            <thead>
              <tr className="text-caps uppercase text-fg-3">
                <th className="py-1.5 font-semibold" />
                <th className="py-1.5 font-semibold">Before patch</th>
                <th className="py-1.5 font-semibold">After patch</th>
              </tr>
            </thead>
            <tbody className="font-mono text-[12.5px]">
              <tr className="border-t border-border/60">
                <td className="py-2 font-sans text-fg-3">Tests</td>
                <td className="py-2">{testsLine(v.tests_before)}</td>
                <td className="py-2">{testsLine(v.tests_after)}</td>
              </tr>
              <tr className="border-t border-border/60">
                <td className="py-2 font-sans text-fg-3">Benchmark</td>
                <td className="py-2">{benchValue(v.bench_before)}</td>
                <td className="py-2">
                  {benchValue(v.bench_after)}
                  {v.improvement != null && (
                    <span className={v.improvement > 0 ? 'ml-2 text-green' : 'ml-2 text-red'}>
                      {v.improvement > 0 ? '−' : '+'}
                      {Math.abs(v.improvement * 100).toFixed(0)}%
                    </span>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="text-fg-3">
            Verification did not run{r.recorded.approval ? ` (patch ${r.recorded.approval.decision})` : ''}.
          </p>
        )}
        {v?.tests_after?.failing_tests?.length ? (
          <p className="mt-3 text-red">Failing: {v.tests_after.failing_tests.join(', ')}</p>
        ) : null}
        {v?.touched_protected?.length ? (
          <p className="mt-3 text-amber">The patch touched protected files (restored for verification): {v.touched_protected.join(', ')}</p>
        ) : null}
      </Section>

      {r.patch_artifact_id && (
        <Section title="Proposed patch" source="recorded">
          <Patch id={r.patch_artifact_id} />
        </Section>
      )}

      {r.review && (
        <Section title={`Review · ${r.review.recommendation.replaceAll('_', ' ')}`} source="model">
          <p className="leading-relaxed text-fg-2">{r.review.assessment}</p>
          {r.review.concerns.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-fg-2">
              {r.review.concerns.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </Section>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Section title="Limitations" source="model">
          <ul className="list-disc space-y-1 pl-5 text-fg-2">
            {r.narrative.limitations.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </Section>
        <Section title="Next steps" source="model">
          <ul className="list-disc space-y-1 pl-5 text-fg-2">
            {r.narrative.next_steps.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </Section>
      </div>

      <Section title="Evidence artifacts" source="recorded">
        <ul className="divide-y divide-border/60 font-mono text-[12px]">
          {evidence.map((a) => (
            <li key={a.id} className="flex items-center justify-between py-2">
              <span>
                <span className="text-cyan">{a.kind}</span> <span className="text-fg">{a.name}</span>
              </span>
              <span className="text-fg-3">
                {a.size_bytes.toLocaleString()} B · sha256 {a.sha256.slice(0, 12)}
              </span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}
