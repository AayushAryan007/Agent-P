import { Pause, Play, RotateCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ExecutionEvent } from '@/domain/events'
import { reduceEvents, type RunState } from '@/domain/runState'
import { formatClock } from '@/lib/format'

const SPEEDS = [0.5, 1, 2, 4, 8] as const
/** Long idle gaps (e.g. waiting for approval) are compressed so replay stays watchable. */
const MAX_GAP_MS = 1500

/**
 * Replays persisted events on a client-side clock. State at position N is
 * reduceEvents(events[0..N)), the same reducer as the live view.
 */
export function useReplay(events: readonly ExecutionEvent[]) {
  // null = "at the end", so newly loaded events show the final state without a sync effect.
  const [cursor, setPosition] = useState<number | null>(null)
  const [wantsPlay, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(2)
  const position = Math.min(cursor ?? events.length, events.length)
  const playing = wantsPlay && position < events.length

  useEffect(() => {
    if (!playing) return
    const prev = events[position - 1]
    const next = events[position]
    const gap = prev && next ? Date.parse(next.occurred_at) - Date.parse(prev.occurred_at) : 0
    const delay = Math.min(Math.max(gap, 0), MAX_GAP_MS) / speed
    const t = setTimeout(() => setPosition(position + 1), delay)
    return () => clearTimeout(t)
  }, [playing, position, events, speed])

  const state: RunState = useMemo(() => reduceEvents(events.slice(0, position)), [events, position])
  const current = events[position - 1]
  const clock = current ? Date.parse(current.occurred_at) : undefined

  return {
    state,
    clock,
    bar: (
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={playing ? 'Pause replay' : 'Play replay'}
          onClick={() => {
            if (!playing && position >= events.length) setPosition(0)
            setPlaying(!playing)
          }}
          className="grid size-7 place-items-center rounded-control bg-blue text-white hover:bg-blue/90"
        >
          {playing ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
        </button>
        <button
          type="button"
          aria-label="Restart replay"
          onClick={() => {
            setPosition(0)
            setPlaying(true)
          }}
          className="grid size-7 place-items-center rounded-control text-fg-2 hover:bg-surface-3"
        >
          <RotateCcw className="size-3.5" />
        </button>
        <input
          type="range"
          min={0}
          max={events.length}
          value={position}
          onChange={(e) => {
            setPlaying(false)
            setPosition(Number(e.target.value))
          }}
          aria-label="Replay position"
          className="w-40 accent-[var(--color-blue)]"
        />
        <span className="w-24 font-mono text-[11px] text-fg-3">
          {position}/{events.length} {current && `· ${formatClock(current.occurred_at).slice(0, 8)}`}
        </span>
        <select
          value={speed}
          onChange={(e) => setSpeed(Number(e.target.value) as (typeof SPEEDS)[number])}
          aria-label="Playback speed"
          className="h-7 rounded-control border border-border bg-surface-2 px-1.5 font-mono text-[11px] text-fg"
        >
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
      </div>
    ),
  }
}
