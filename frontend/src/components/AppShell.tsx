import * as Tooltip from '@radix-ui/react-tooltip'
import clsx from 'clsx'
import { LayoutDashboard, ListTree, Plus, Settings, type LucideIcon } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { API_URL } from '@/api/client'
import { useMe } from '@/api/queries'
import { Button } from './ui'

const NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/runs', label: 'Runs', icon: ListTree },
  { to: '/tasks/new', label: 'New task', icon: Plus },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--color-surface-2)" stroke="var(--color-border-strong)" />
      <circle cx="9" cy="16" r="3.2" fill="var(--color-blue)" />
      <circle cx="23" cy="9.5" r="3.2" fill="var(--color-violet)" />
      <circle cx="23" cy="22.5" r="3.2" fill="var(--color-green)" />
      <path d="M12 15l8-4.5M12 17l8 4.5" stroke="var(--color-cyan)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function ConnectionChip() {
  const me = useMe()
  const state = me.isPending ? 'checking' : me.isError ? 'offline' : 'online'
  const tone = { checking: 'bg-slate', offline: 'bg-red', online: 'bg-green' }[state]
  const label = { checking: 'Connecting…', offline: 'Backend offline', online: 'Connected' }[state]
  return (
    <div className="flex items-center gap-3">
      <span className="flex items-center gap-2 text-[12px] text-fg-3" title={API_URL}>
        <span className={clsx('size-2 rounded-full', tone)} aria-hidden />
        {label}
      </span>
      {me.data && (
        <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-fg-2">
          {me.data.role === 'operator' ? 'Operator' : 'Viewer'}
        </span>
      )}
    </div>
  )
}

export function AppShell() {
  const navigate = useNavigate()
  return (
    <Tooltip.Provider delayDuration={300}>
      <div className="flex h-full">
        <nav aria-label="Primary" className="flex w-16 shrink-0 flex-col items-center gap-1 border-r border-border bg-surface-1 py-3">
          <NavLink to="/" aria-label="AGENT-P home" className="mb-4">
            <Logo />
          </NavLink>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <Tooltip.Root key={to}>
              <Tooltip.Trigger asChild>
                <NavLink
                  to={to}
                  end={end}
                  aria-label={label}
                  className={({ isActive }) =>
                    clsx(
                      'relative grid size-10 place-items-center rounded-control transition-colors',
                      isActive
                        ? 'bg-blue/12 text-blue before:absolute before:-left-3 before:h-5 before:w-0.5 before:rounded-full before:bg-blue'
                        : 'text-fg-3 hover:bg-surface-3 hover:text-fg',
                    )
                  }
                >
                  <Icon className="size-[18px]" aria-hidden />
                </NavLink>
              </Tooltip.Trigger>
              <Tooltip.Portal>
                <Tooltip.Content
                  side="right"
                  sideOffset={8}
                  className="rounded-control border border-border bg-surface-2 px-2 py-1 text-[12px] text-fg shadow-lg"
                >
                  {label}
                </Tooltip.Content>
              </Tooltip.Portal>
            </Tooltip.Root>
          ))}
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-6">
            <div className="flex items-baseline gap-3">
              <span className="text-[15px] font-semibold tracking-wide">AGENT-P</span>
              <span className="hidden text-[12px] text-fg-3 sm:inline">Agent execution &amp; observability</span>
            </div>
            <div className="flex items-center gap-4">
              <ConnectionChip />
              <Button variant="primary" icon={Plus} onClick={() => navigate('/tasks/new')}>
                New task
              </Button>
            </div>
          </header>
          <main className="min-h-0 flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </Tooltip.Provider>
  )
}
