import clsx from 'clsx'
import { ListTree } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { useRuns } from '@/api/queries'
import { EmptyState, ErrorState, Panel, Skeleton } from '@/components/ui'
import { RunsTable } from './RunsTable'

const FILTERS = [
  { value: undefined, label: 'All' },
  { value: 'running', label: 'Running' },
  { value: 'waiting_approval', label: 'Awaiting approval' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
] as const

export function RunsPage() {
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? undefined
  const setStatus = (s: string | undefined) => setParams(s ? { status: s } : {})
  const runs = useRuns(status, 50)

  return (
    <div className="p-6">
      <Panel
        title="Runs"
        bodyClassName="p-0"
        actions={
          <div className="flex gap-1" role="group" aria-label="Filter by status">
            {FILTERS.map((f) => (
              <button
                key={f.label}
                type="button"
                aria-pressed={status === f.value}
                onClick={() => setStatus(f.value)}
                className={clsx(
                  'h-7 rounded-control px-2.5 text-[12px]',
                  status === f.value ? 'bg-surface-3 text-fg' : 'text-fg-3 hover:text-fg',
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        }
      >
        {runs.isPending ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        ) : runs.isError ? (
          <ErrorState error={runs.error} onRetry={() => runs.refetch()} />
        ) : runs.data.items.length === 0 ? (
          <EmptyState icon={ListTree} title="No runs">
            {status ? 'No runs match this filter.' : 'Runs appear here once a task is started.'}
          </EmptyState>
        ) : (
          <RunsTable runs={runs.data.items} />
        )}
      </Panel>
    </div>
  )
}
