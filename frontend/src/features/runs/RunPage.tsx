import { useQuery } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { useParams } from 'react-router'
import { useRun } from '@/api/queries'
import { ErrorState, Skeleton } from '@/components/ui'
import { isTerminal } from '@/domain/runState'
import { RunWorkspace } from '@/features/workspace/RunWorkspace'
import { fetchAllEvents, useLiveRunEvents, type StreamStatus } from './useRunEvents'
import { useReplay } from './useReplay'
import type { ExecutionEvent } from '@/domain/events'

const STREAM_LABEL: Record<StreamStatus, [string, string]> = {
  connecting: ['Connecting', 'bg-slate'],
  live: ['Live', 'bg-green'],
  reconnecting: ['Reconnecting', 'bg-amber'],
  ended: ['Stream ended', 'bg-slate'],
  error: ['Stream error', 'bg-red'],
}

export function RecordedBanner() {
  return (
    <div className="flex h-8 shrink-0 items-center gap-2 border-b border-border bg-surface-2 px-6 text-[12px] text-fg-2">
      <History className="size-3.5 text-cyan" aria-hidden />
      <span className="font-semibold uppercase tracking-wider text-cyan">Recorded</span>
      <span className="text-fg-3">Replaying persisted events. No model calls are made.</span>
    </div>
  )
}

function LiveRun({ runId, title }: { runId: string; title: string }) {
  const { state, stream } = useLiveRunEvents(runId, true)
  const [label, dot] = STREAM_LABEL[stream]
  return (
    <RunWorkspace
      title={title}
      state={state}
      toolbar={
        <span className="flex items-center gap-1.5">
          <span className={`size-2 rounded-full ${dot}`} aria-hidden />
          {label}
        </span>
      }
    />
  )
}

function RecordedRun({ title, events }: { title: string; events: ExecutionEvent[] }) {
  const replay = useReplay(events)
  return <RunWorkspace title={title} state={replay.state} banner={<RecordedBanner />} toolbar={replay.bar} nowOverride={replay.clock} />
}

function RecordedRunLoader({ runId, title }: { runId: string; title: string }) {
  const events = useQuery({
    queryKey: ['run-events', runId],
    queryFn: ({ signal }) => fetchAllEvents(runId, signal),
    staleTime: Infinity,
  })
  if (events.isPending) return <Skeleton className="m-6 h-[600px]" />
  if (events.isError) return <ErrorState error={events.error} onRetry={() => events.refetch()} />
  return <RecordedRun title={title} events={events.data} />
}

export function RunPage() {
  const { runId = '' } = useParams()
  const run = useRun(runId)
  if (run.isPending) return <Skeleton className="m-6 h-[600px]" />
  if (run.isError) return <ErrorState error={run.error} onRetry={() => run.refetch()} />
  return isTerminal(run.data.status) ? (
    <RecordedRunLoader runId={runId} title={run.data.task_title} />
  ) : (
    <LiveRun runId={runId} title={run.data.task_title} />
  )
}
