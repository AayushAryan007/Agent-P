import { FlaskConical } from 'lucide-react'
import { illustrativeEvents } from '@/fixtures/illustrativeRun'
import { useReplay } from '@/features/runs/useReplay'
import { RunWorkspace } from '@/features/workspace/RunWorkspace'

/** Dev-only design preview. Clearly labeled: the data is a fixture, not a real execution. */
export function DevPreviewPage() {
  const replay = useReplay(illustrativeEvents)
  return (
    <RunWorkspace
      title="Slow GET /orders endpoint"
      state={replay.state}
      nowOverride={replay.clock}
      initialStepId="s-anl"
      readOnly
      toolbar={replay.bar}
      banner={
        <div className="flex h-8 shrink-0 items-center gap-2 border-b border-amber/30 bg-amber/10 px-6 text-[12px]">
          <FlaskConical className="size-3.5 text-amber" aria-hidden />
          <span className="font-semibold uppercase tracking-wider text-amber">Illustrative</span>
          <span className="text-fg-2">Hand-written fixture events for design review. Not a real execution. Dev builds only.</span>
        </div>
      }
    />
  )
}
