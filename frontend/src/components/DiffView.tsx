import clsx from 'clsx'
import { useMemo } from 'react'
import { parseUnifiedDiff } from '@/lib/diff'

export function DiffView({ diff, maxHeight = 420 }: { diff: string; maxHeight?: number }) {
  const files = useMemo(() => parseUnifiedDiff(diff), [diff])
  if (files.length === 0) return <p className="text-fg-3">Empty diff.</p>
  return (
    <div className="space-y-3">
      {files.map((f) => (
        <div key={f.path} className="overflow-hidden rounded-control border border-border">
          <div className="flex items-center justify-between border-b border-border bg-surface-2 px-3 py-1.5 font-mono text-[12px]">
            <span className="truncate text-fg">{f.path}</span>
            <span>
              <span className="text-green">+{f.additions}</span> <span className="text-red">−{f.deletions}</span>
            </span>
          </div>
          <pre className="overflow-auto bg-bg font-mono text-[11.5px] leading-[1.55]" style={{ maxHeight }}>
            {f.lines.map((l, i) => (
              <div
                key={i}
                className={clsx(
                  'px-3',
                  l.startsWith('+') && 'bg-green/10 text-green',
                  l.startsWith('-') && 'bg-red/10 text-red',
                  l.startsWith('@@') && 'bg-blue/8 text-blue',
                  !/^[+\-@]/.test(l) && 'text-fg-2',
                )}
              >
                {l || ' '}
              </div>
            ))}
          </pre>
        </div>
      ))}
    </div>
  )
}
