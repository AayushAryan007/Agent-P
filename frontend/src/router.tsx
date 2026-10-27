import { createBrowserRouter, type RouteObject } from 'react-router'
import { AppShell } from '@/components/AppShell'
import { NotFound } from '@/components/NotFound'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { LandingPage } from '@/features/landing/LandingPage'
import { RunsPage } from '@/features/runs/RunsPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { NewTaskPage } from '@/features/tasks/NewTaskPage'

const children: RouteObject[] = [
  { path: 'dashboard', element: <DashboardPage /> },
  { path: 'runs', element: <RunsPage /> },
  // The workspace pulls in React Flow + ELK (~1.5 MB), so it loads on demand.
  { path: 'runs/:runId', lazy: async () => ({ Component: (await import('@/features/runs/RunPage')).RunPage }) },
  { path: 'runs/:runId/report', lazy: async () => ({ Component: (await import('@/features/runs/ReportPage')).ReportPage }) },
  { path: 'tasks/new', element: <NewTaskPage /> },
  { path: 'settings', element: <SettingsPage /> },
  { path: '*', element: <NotFound /> },
]

// The illustrative preview (and its fixture) is excluded from production bundles.
if (import.meta.env.DEV) {
  children.push({
    path: 'dev/preview',
    lazy: async () => ({ Component: (await import('@/features/dev/DevPreviewPage')).DevPreviewPage }),
  })
}

export const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  { element: <AppShell />, children },
])
