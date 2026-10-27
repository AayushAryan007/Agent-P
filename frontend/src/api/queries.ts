import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { CreateTaskRequest, Me, Meta, MetricsSummary, Page, RunDetail, RunListItem, Task } from './types'

export const queryKeys = {
  me: ['me'] as const,
  meta: ['meta'] as const,
  metrics: (window: string) => ['metrics', window] as const,
  runs: (status?: string) => ['runs', status ?? 'all'] as const,
  run: (id: string) => ['run', id] as const,
}

export const useMe = () => useQuery({ queryKey: queryKeys.me, queryFn: ({ signal }) => api<Me>('/auth/me', { signal }) })

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
