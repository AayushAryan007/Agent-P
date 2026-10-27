import { useEffect, useReducer, useState } from 'react'
import { api, eventStreamUrl } from '@/api/client'
import type { EventsPage } from '@/api/types'
import type { ExecutionEvent } from '@/domain/events'
import { applyEvent, initialRunState, type RunState } from '@/domain/runState'

export type StreamStatus = 'connecting' | 'live' | 'reconnecting' | 'ended' | 'error'

/**
 * Live run state from the SSE stream. The server replays everything after
 * `after_seq`, and EventSource resends Last-Event-ID on reconnect; the
 * reducer drops duplicates by sequence number, so delivery is effectively
 * exactly-once in the rendered state (docs/API_SPECIFICATION.md §4).
 */
export function useLiveRunEvents(runId: string, enabled: boolean): { state: RunState; stream: StreamStatus } {
  const [state, dispatch] = useReducer(applyEvent, initialRunState)
  const [stream, setStream] = useState<StreamStatus>('connecting')

  useEffect(() => {
    if (!enabled) return
    const es = new EventSource(eventStreamUrl(runId, 0), { withCredentials: true })
    es.onopen = () => setStream('live')
    es.onmessage = (msg) => {
      try {
        dispatch(JSON.parse(msg.data) as ExecutionEvent)
      } catch {
        // A malformed frame must not break the stream; the next catch-up will repair state.
      }
    }
    es.addEventListener('end', () => {
      setStream('ended')
      es.close()
    })
    es.onerror = () => setStream(es.readyState === EventSource.CLOSED ? 'error' : 'reconnecting')
    return () => es.close()
  }, [runId, enabled])

  return { state, stream }
}

/** All persisted events for a run, paged. Used by replay; never triggers model calls. */
export async function fetchAllEvents(runId: string, signal?: AbortSignal): Promise<ExecutionEvent[]> {
  const out: ExecutionEvent[] = []
  let after: number | null = 0
  while (after != null) {
    const page: EventsPage = await api<EventsPage>(`/runs/${runId}/events?after_seq=${after}&limit=500`, { signal })
    out.push(...page.items)
    after = page.next_after_seq
  }
  return out
}
