import { useNavigate } from 'react-router'
import type { RunListItem } from '@/api/types'
import { StatusBadge, VerificationBadge } from '@/components/ui'
import { durationBetween, formatDuration, formatRelative, formatTokens } from '@/lib/format'

export function RunsTable({ runs }: { runs: RunListItem[] }) {
  const navigate = useNavigate()
  return (
    <table className="w-full text-left">
      <thead>
        <tr className="border-b border-border text-caps uppercase text-fg-3">
          <th className="px-4 py-2 font-semibold">Task</th>
          <th className="px-4 py-2 font-semibold">Status</th>
          <th className="px-4 py-2 font-semibold">Verification</th>
          <th className="px-4 py-2 text-right font-semibold">Duration</th>
          <th className="px-4 py-2 text-right font-semibold">Tokens</th>
          <th className="px-4 py-2 text-right font-semibold">Queued</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr
            key={r.id}
            tabIndex={0}
            onClick={() => navigate(`/runs/${r.id}`)}
            onKeyDown={(e) => e.key === 'Enter' && navigate(`/runs/${r.id}`)}
            className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-surface-2 focus-visible:bg-surface-2"
          >
            <td className="max-w-80 truncate px-4 py-2.5 text-fg">{r.task_title}</td>
            <td className="px-4 py-2.5">
              <StatusBadge status={r.status} />
            </td>
            <td className="px-4 py-2.5">
              <VerificationBadge label={r.verification_label} />
            </td>
            <td className="px-4 py-2.5 text-right font-mono text-fg-2">
              {formatDuration(durationBetween(r.started_at, r.finished_at))}
            </td>
            <td className="px-4 py-2.5 text-right font-mono text-fg-2">
              {formatTokens(r.totals.input_tokens + r.totals.output_tokens)}
            </td>
            <td className="px-4 py-2.5 text-right text-fg-3">{formatRelative(r.queued_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
