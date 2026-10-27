import { CheckCircle2, CircleDashed } from 'lucide-react'
import { useMeta } from '@/api/queries'
import { ErrorState, Panel, Skeleton } from '@/components/ui'

/** Read-only for now; provider keys are configured on the backend and never sent to the browser (FR-31). */
export function SettingsPage() {
  const meta = useMeta()
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <Panel title="Model providers" bodyClassName="p-0">
        {meta.isPending ? (
          <Skeleton className="m-4 h-24" />
        ) : meta.isError ? (
          <ErrorState error={meta.error} onRetry={() => meta.refetch()} />
        ) : (
          <ul className="divide-y divide-border/60">
            {meta.data.providers.map((p) => (
              <li key={p.name} className="flex items-start gap-3 px-4 py-3.5">
                {p.configured ? (
                  <CheckCircle2 className="mt-0.5 size-4 text-green" aria-label="Configured" />
                ) : (
                  <CircleDashed className="mt-0.5 size-4 text-fg-3" aria-label="Not configured" />
                )}
                <div className="flex-1">
                  <div className="font-medium capitalize">{p.name}</div>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {p.models.map((m) => (
                      <span key={m.id} className="rounded-full border border-border px-2 py-0.5 font-mono text-[11px] text-fg-2">
                        {m.id}
                        {m.role !== 'available' && <span className="text-fg-3"> · {m.role}</span>}
                      </span>
                    ))}
                  </div>
                </div>
                <span className="text-[12px] text-fg-3">{p.configured ? 'Key set on server' : 'No key on server'}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <p className="text-[12px] text-fg-3">
        API keys live only in the backend environment. They are never returned by the API, stored in the database, or included in logs.
      </p>
    </div>
  )
}
