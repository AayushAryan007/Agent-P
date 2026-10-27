import { Check, Hand, X } from 'lucide-react'
import { useState } from 'react'
import { ApiError } from '@/api/client'
import { useApprovalDecision, useArtifact, useMe } from '@/api/queries'
import { DiffView } from '@/components/DiffView'
import { Button, Skeleton } from '@/components/ui'
import type { ApprovalState } from '@/domain/runState'

/** Human approval gate (FR-15): shows the exact patch that will be applied to a temporary copy. */
export function ApprovalCard({ approval, readOnly }: { approval: ApprovalState; readOnly?: boolean }) {
  const me = useMe()
  const patch = useArtifact(approval.artifactId)
  const decide = useApprovalDecision()
  const [comment, setComment] = useState('')
  const pending = approval.status === 'pending'
  const canDecide = pending && !readOnly && me.data?.role === 'operator'
  const rationale = typeof patch.data?.data?.rationale === 'string' ? patch.data.data.rationale : null

  return (
    <div className="rounded-panel border border-amber/40 bg-amber/5">
      <div className="flex items-center gap-2 border-b border-amber/20 px-4 py-2.5">
        <Hand className="size-4 text-amber" aria-hidden />
        <span className="text-caps font-semibold uppercase text-amber">
          {pending ? 'Approval required' : `Patch ${approval.status}`}
        </span>
      </div>
      <div className="space-y-3 p-4">
        {approval.summary && <p className="text-fg">{approval.summary}</p>}
        {rationale && <p className="text-fg-2">{rationale}</p>}
        {patch.isPending ? (
          <Skeleton className="h-40" />
        ) : patch.isError ? (
          <p className="text-red">Could not load the patch.</p>
        ) : (
          <DiffView diff={patch.data.text ?? ''} maxHeight={300} />
        )}
        <p className="text-[12px] text-fg-3">
          Approving applies this patch to a temporary copy of the repository and runs the original tests and benchmark in the
          sandbox. Nothing outside the sandbox is modified.
        </p>
        {approval.comment && <p className="text-[12px] text-fg-2">Comment: “{approval.comment}”</p>}
        {canDecide && (
          <>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Optional comment"
              maxLength={2000}
              className="w-full rounded-control border border-border bg-bg px-3 py-2 text-fg placeholder:text-fg-3 focus:border-blue focus:outline-none"
            />
            {decide.isError && (
              <p className="text-[12px] text-red">{decide.error instanceof ApiError ? decide.error.message : 'Decision failed'}</p>
            )}
            <div className="flex gap-2">
              <Button
                variant="primary"
                icon={Check}
                loading={decide.isPending && decide.variables.decision === 'approve'}
                disabled={decide.isPending || decide.isSuccess}
                onClick={() => decide.mutate({ id: approval.id, decision: 'approve', comment })}
              >
                Approve &amp; verify
              </Button>
              <Button
                variant="danger"
                icon={X}
                loading={decide.isPending && decide.variables.decision === 'reject'}
                disabled={decide.isPending || decide.isSuccess}
                onClick={() => decide.mutate({ id: approval.id, decision: 'reject', comment })}
              >
                Reject
              </Button>
            </div>
          </>
        )}
        {pending && !readOnly && me.data?.role !== 'operator' && (
          <p className="text-[12px] text-fg-3">Only the operator can approve or reject.</p>
        )}
      </div>
    </div>
  )
}
