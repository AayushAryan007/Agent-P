import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, setCsrfToken } from './client'
import type {
  ArtifactMeta,
  ArtifactOut,
  CreateTaskRequest,
  Me,
  Meta,
  MetricsSummary,
  Page,
  RunDetail,
  RunListItem,
  Task,
} from './types'

export const queryKeys = {
  me: ['me'] as const,
  meta: ['meta'] as const,
  metrics: (window: string) => ['metrics', window] as const,
  runs: (status?: string) => ['runs', status ?? 'all'] as const,
  run: (id: string) => ['run', id] as const,
}

async function fetchMe(signal?: AbortSignal): Promise<Me> {
  const me = await api<Me>('/auth/me', { signal })
  setCsrfToken(me.csrf_token)
  return me
}

export const useMe = () => useQuery({ queryKey: queryKeys.me, queryFn: ({ signal }) => fetchMe(signal) })

export function useSignIn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => api<Me>('/auth/session', { method: 'POST', body: { token } }),
    onSuccess: (me) => {
      setCsrfToken(me.csrf_token)
      qc.setQueryData(queryKeys.me, me)
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
    },
  })
}

export function useSignOut() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>('/auth/session', { method: 'DELETE' }),
    onSuccess: () => {
      setCsrfToken(null)
      qc.setQueryData(queryKeys.me, { role: 'anonymous', csrf_token: null } satisfies Me)
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
    },
  })
}

export const useMeta = () =>
  useQuery({ queryKey: queryKeys.meta, queryFn: ({ signal }) => api<Meta>('/meta', { signal }), staleTime: 5 * 60_000 })

export const useMetrics = (window = '7d') =>
  useQuery({
    queryKey: queryKeys.metrics(window),
    queryFn: ({ signal }) => api<MetricsSummary>(`/metrics/summary?window=${window}`, { signal }),
    refetchInterval: 15_000,
  })

export const useRuns = (status?: string, limit = 20) =>
  useQuery({
    queryKey: queryKeys.runs(status),
    queryFn: ({ signal }) => {
      const qs = new URLSearchParams({ limit: String(limit) })
      if (status) qs.set('status', status)
      return api<Page<RunListItem>>(`/runs?${qs}`, { signal })
    },
    refetchInterval: 10_000,
  })

export const useRun = (id: string) =>
  useQuery({ queryKey: queryKeys.run(id), queryFn: ({ signal }) => api<RunDetail>(`/runs/${id}`, { signal }) })

export function useCreateTaskAndRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (req: CreateTaskRequest) => {
      const task = await api<Task>('/tasks', { method: 'POST', body: req })
      return api<RunListItem>(`/tasks/${task.id}/runs`, {
        method: 'POST',
        body: {},
        idempotencyKey: crypto.randomUUID(),
      })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
  })
}

export const useArtifact = (id: string | null) =>
  useQuery({
    queryKey: ['artifact', id],
    queryFn: ({ signal }) => api<ArtifactOut>(`/artifacts/${id}`, { signal }),
    enabled: !!id,
    staleTime: Infinity, // artifacts are immutable
  })

export const useRunArtifacts = (runId: string) =>
  useQuery({
    queryKey: ['run-artifacts', runId],
    queryFn: ({ signal }) => api<ArtifactMeta[]>(`/runs/${runId}/artifacts`, { signal }),
  })

export function useApprovalDecision() {
  return useMutation({
    mutationFn: ({ id, decision, comment }: { id: string; decision: 'approve' | 'reject'; comment?: string }) =>
      api(`/approvals/${id}/decision`, {
        method: 'POST',
        body: { decision, comment: comment || null },
        idempotencyKey: crypto.randomUUID(),
      }),
  })
}

export function useCancelRun() {
  return useMutation({ mutationFn: (runId: string) => api(`/runs/${runId}/cancel`, { method: 'POST' }) })
}
