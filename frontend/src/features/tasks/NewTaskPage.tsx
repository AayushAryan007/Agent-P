import clsx from 'clsx'
import { Box, GitBranch, Hand, Lock, Play, ShieldCheck, Timer, WifiOff } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { ApiError } from '@/api/client'
import { useCreateTaskAndRun, useMe, useMeta } from '@/api/queries'
import type { Limits, Meta, RepoSource } from '@/api/types'
import { Button, ErrorState, Panel, Skeleton } from '@/components/ui'

/** Same rule as the backend (ADR-0003): public github.com HTTPS repos only. */
const GITHUB_URL = /^https:\/\/github\.com\/[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100}?(\.git)?\/?$/

const LIMIT_FIELDS: { key: keyof Limits; label: string; unit: string }[] = [
  { key: 'max_minutes', label: 'Wall time', unit: 'min' },
  { key: 'max_llm_calls', label: 'LLM calls', unit: 'calls' },
  { key: 'max_total_tokens', label: 'Tokens', unit: 'tokens' },
  { key: 'max_tool_calls', label: 'Tool calls', unit: 'calls' },
]

const inputClass =
  'w-full rounded-control border border-border bg-surface-2 px-3 py-2 text-fg placeholder:text-fg-3 hover:border-border-strong focus:border-blue focus:outline-none'

function Label({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-1.5 flex items-baseline justify-between">
      <span className="text-caps font-semibold uppercase text-fg-2">{children}</span>
      {hint && <span className="text-[11px] text-fg-3">{hint}</span>}
    </div>
  )
}

function Form({ meta, isOperator }: { meta: Meta; isOperator: boolean }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const create = useCreateTaskAndRun()

  const defaultModel = meta.providers.flatMap((p) => (p.configured ? p.models : [])).find((m) => m.role === 'default')
  const [templateKey, setTemplateKey] = useState(params.get('template') ?? meta.templates[0]?.key ?? '')
  const [title, setTitle] = useState('')
  const [goal, setGoal] = useState('')
  const [repoKind, setRepoKind] = useState<RepoSource['kind']>('bundled')
  const [bundledKey, setBundledKey] = useState(meta.bundled_repos[0]?.key ?? '')
  const [githubUrl, setGithubUrl] = useState('')
  const [model, setModel] = useState(defaultModel?.id ?? '')
  const [limits, setLimits] = useState<Limits>(meta.limits_default)

  const template = meta.templates.find((t) => t.key === templateKey)
  const configuredModels = meta.providers.filter((p) => p.configured).flatMap((p) => p.models.map((m) => ({ ...m, provider: p.name })))

  const errors = useMemo(() => {
    const e: Partial<Record<'title' | 'goal' | 'repo' | 'model' | keyof Limits, string>> = {}
    if (!title.trim()) e.title = 'Required'
    if (goal.trim().length < 20) e.goal = 'Describe the task in at least 20 characters'
    if (repoKind === 'github' && !GITHUB_URL.test(githubUrl.trim())) e.repo = 'Must be https://github.com/<owner>/<repo>'
    if (repoKind === 'bundled' && !bundledKey) e.repo = 'Choose a repository'
    if (!model) e.model = 'No configured model'
    for (const f of LIMIT_FIELDS) {
      const v = limits[f.key]
      if (!Number.isInteger(v) || v < 1 || v > meta.limits_max[f.key]) e[f.key] = `1 – ${meta.limits_max[f.key]}`
    }
    return e
  }, [title, goal, repoKind, githubUrl, bundledKey, model, limits, meta.limits_max])
  const valid = Object.keys(errors).length === 0 && !!template

  const submit = () => {
    if (!valid || !template) return
    create.mutate(
      {
        title: title.trim(),
        goal: goal.trim(),
        template_key: template.key,
        repo_source: repoKind === 'bundled' ? { kind: 'bundled', key: bundledKey } : { kind: 'github', url: githubUrl.trim() },
        model,
        limits,
        visibility: repoKind === 'bundled' ? 'public' : 'private',
      },
      { onSuccess: (run) => navigate(`/runs/${run.id}`) },
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
      <Panel title="Task">
        <form
          className="space-y-6"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <div>
            <Label>Workflow template</Label>
            <div className="grid gap-3 md:grid-cols-2" role="radiogroup">
              {meta.templates.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="radio"
                  aria-checked={t.key === templateKey}
                  onClick={() => setTemplateKey(t.key)}
                  className={clsx(
                    'rounded-panel border p-3.5 text-left transition-colors',
                    t.key === templateKey ? 'border-blue bg-blue/8' : 'border-border bg-surface-2 hover:border-border-strong',
                  )}
                >
                  <div className="font-medium">{t.title}</div>
                  <p className="mt-1 text-fg-3">{t.description}</p>
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label hint={errors.title && title ? errors.title : undefined}>Title</Label>
            <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="Slow GET /orders endpoint" />
          </div>

          <div>
            <Label hint={goal && errors.goal}>Goal</Label>
            <textarea
              className={clsx(inputClass, 'min-h-28 resize-y leading-relaxed')}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              maxLength={4000}
              placeholder="Investigate why GET /orders is slow, identify the root cause, propose a fix, and verify that the fix works."
            />
          </div>

          <div>
            <Label hint={repoKind === 'github' && githubUrl ? errors.repo : undefined}>Repository</Label>
            <div className="mb-3 inline-flex rounded-control border border-border bg-surface-2 p-0.5" role="radiogroup">
              {(
                [
                  ['bundled', 'Bundled demo', Box],
                  ['github', 'Public GitHub URL', GitBranch],
                ] as const
              ).map(([kind, label, Icon]) => (
                <button
                  key={kind}
                  type="button"
                  role="radio"
                  aria-checked={repoKind === kind}
                  onClick={() => setRepoKind(kind)}
                  className={clsx(
                    'flex h-7 items-center gap-1.5 rounded-[5px] px-3 text-[12px]',
                    repoKind === kind ? 'bg-surface-3 text-fg' : 'text-fg-3 hover:text-fg',
                  )}
                >
                  <Icon className="size-3.5" aria-hidden />
                  {label}
                </button>
              ))}
            </div>
            {repoKind === 'bundled' ? (
              <select className={inputClass} value={bundledKey} onChange={(e) => setBundledKey(e.target.value)}>
                {meta.bundled_repos.map((r) => (
                  <option key={r.key} value={r.key}>
                    {r.title} — {r.description}
                  </option>
                ))}
              </select>
            ) : (
              <>
                <input
                  className={clsx(inputClass, 'font-mono')}
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  spellCheck={false}
                />
                <p className="mt-1.5 text-[12px] text-fg-3">
                  Shallow clone, ≤ 50 MB, no submodules. Runs on GitHub repos are private by default.
                </p>
              </>
            )}
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <Label hint={errors.model}>Model</Label>
              <select className={clsx(inputClass, 'font-mono')} value={model} onChange={(e) => setModel(e.target.value)}>
                {configuredModels.map((m) => (
                  <option key={`${m.provider}:${m.id}`} value={m.id}>
                    {m.id} ({m.provider}
                    {m.role !== 'available' ? `, ${m.role}` : ''})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <Label>Execution limits</Label>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {LIMIT_FIELDS.map((f) => (
                <label key={f.key} className="block">
                  <span className="mb-1 block text-[12px] text-fg-3">
                    {f.label} <span className="text-fg-3/70">(max {meta.limits_max[f.key].toLocaleString()})</span>
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={meta.limits_max[f.key]}
                    className={clsx(inputClass, 'font-mono', errors[f.key] && 'border-red/60')}
                    value={limits[f.key]}
                    onChange={(e) => setLimits({ ...limits, [f.key]: Number(e.target.value) })}
                  />
                </label>
              ))}
            </div>
          </div>

          {create.isError && (
            <div role="alert" className="rounded-control border border-red/30 bg-red/10 p-3 text-red">
              {create.error instanceof ApiError ? create.error.message : 'Could not start the run.'}
            </div>
          )}
          <div className="flex items-center justify-end gap-3 border-t border-border pt-5">
            {!isOperator && (
              <span className="flex items-center gap-1.5 text-[12px] text-fg-3">
                <Lock className="size-3.5" aria-hidden /> Operator sign-in required to start runs
              </span>
            )}
            <Button type="submit" variant="primary" icon={Play} disabled={!valid || !isOperator} loading={create.isPending}>
              Start run
            </Button>
          </div>
        </form>
      </Panel>

      <div className="xl:sticky xl:top-6 xl:self-start">
        <Panel title="This run is authorized to">
          <ul className="space-y-3">
            {template?.tools.map((t) => (
              <li key={t.name} className="flex gap-3">
                <span className="mt-0.5 font-mono text-[12px] text-cyan">{t.name}</span>
                <span className="flex-1 text-fg-2">
                  {t.description}
                  {t.runs_in === 'sandbox' && <span className="ml-1 text-fg-3">· in sandbox</span>}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-5 space-y-3 border-t border-border pt-4 text-fg-2">
            <p className="flex gap-2.5">
              <WifiOff className="mt-0.5 size-4 shrink-0 text-cyan" aria-hidden />
              Tests and benchmarks run in an isolated container with no network, as a non-root user, with CPU, memory and time limits.
            </p>
            <p className="flex gap-2.5">
              <Hand className="mt-0.5 size-4 shrink-0 text-amber" aria-hidden />
              Any proposed patch waits for your approval before it is applied, and only to a temporary copy.
            </p>
            <p className="flex gap-2.5">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-green" aria-hidden />
              Verification labels come from real exit codes and test output, never from model text.
            </p>
            <p className="flex gap-2.5">
              <Timer className="mt-0.5 size-4 shrink-0 text-fg-3" aria-hidden />
              The run stops at {limits.max_minutes} min, {limits.max_llm_calls} LLM calls or {limits.max_total_tokens.toLocaleString()} tokens.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  )
}

export function NewTaskPage() {
  const meta = useMeta()
  const me = useMe()
  return (
    <div className="mx-auto max-w-[1400px] p-6">
      {meta.isPending ? (
        <Skeleton className="h-[600px]" />
      ) : meta.isError ? (
        <Panel>
          <ErrorState error={meta.error} onRetry={() => meta.refetch()} />
        </Panel>
      ) : (
        <Form meta={meta.data} isOperator={me.data?.role === 'operator'} />
      )}
    </div>
  )
}
