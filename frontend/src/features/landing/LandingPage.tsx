import '@fontsource-variable/manrope'
import './landing.css'
import { ArrowUpRight, Eye, GitBranch, Hand, PlayCircle, ShieldCheck, Workflow } from 'lucide-react'
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { Link } from 'react-router'
import { useMetrics } from '@/api/queries'
import { BrandLogo } from '@/components/BrandLogo'
import { VideoBackground } from './VideoBackground'

/** 960x540 encode of the background loop; it is blurred, so higher resolution would only cost bandwidth. */
const BACKGROUND_VIDEO = '/bg1-540.mp4'

const delay = (d: number) => ({ '--d': d }) as CSSProperties

function useCountUp(target: number | null, startDelayMs = 900, durationMs = 1200): number | null {
  const [value, setValue] = useState<number | null>(null)
  useEffect(() => {
    if (target == null) return
    let raf = 0
    const t0 = performance.now() + startDelayMs
    const tick = (now: number) => {
      const k = Math.min(1, Math.max(0, (now - t0) / durationMs))
      setValue(target * (1 - Math.pow(1 - k, 3)))
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, startDelayMs, durationMs])
  return value
}

function StatCard({
  value,
  suffix,
  caption,
  d,
}: {
  value: number | null
  suffix?: string
  caption: string
  d: number
}) {
  const shown = useCountUp(value, 900 + d * 150)
  return (
    <div className="glass reveal-right flex min-h-[150px] items-start justify-between rounded-[22px] p-6" style={delay(d)}>
      <div className="flex h-full flex-col justify-between gap-6">
        <div className="text-[44px] font-light leading-none tracking-tight tabular-nums md:text-[54px]">
          {shown == null ? '—' : Math.round(shown).toLocaleString()}
          {suffix && shown != null && <span className="ml-1 text-[26px] font-normal text-[var(--l-mute)]">{suffix}</span>}
        </div>
        <p className="max-w-[220px] text-[13px] leading-snug text-[var(--l-mute)]">{caption}</p>
      </div>
      <div className="orb shrink-0" style={{ animationDelay: `${-d * 2}s` }} aria-hidden />
    </div>
  )
}

function NavItem({ to, children, external }: { to: string; children: ReactNode; external?: boolean }) {
  const cls = 'rounded-full px-4 py-2 text-[14px] text-[var(--l-mute)] transition-colors hover:bg-white/8 hover:text-white'
  return external ? (
    <a href={to} className={cls} target="_blank" rel="noreferrer">
      {children}
    </a>
  ) : to.startsWith('#') ? (
    <a href={to} className={cls}>
      {children}
    </a>
  ) : (
    <Link to={to} className={cls}>
      {children}
    </Link>
  )
}

const STEPS = [
  { icon: Workflow, title: 'Plan', body: 'A coordinator turns your task into a dependency graph of specialised agents.' },
  { icon: Eye, title: 'Inspect', body: 'Agents read and search the repo through typed, permission-checked tools — every call recorded.' },
  { icon: Hand, title: 'Approve', body: 'A proposed patch waits for you. Nothing is applied without an explicit human decision.' },
  { icon: ShieldCheck, title: 'Verify', body: 'Original tests and benchmarks run in a network-less sandbox. Labels come from exit codes, not the model.' },
]

export function LandingPage() {
  const metrics = useMetrics('30d')
  const m = metrics.data
  const live = metrics.isSuccess

  useEffect(() => {
    const prev = document.title
    document.title = 'AGENT-P — watch AI agents work, verify what they claim'
    return () => {
      document.title = prev
    }
  }, [])

  return (
    <div className="landing relative min-h-full overflow-x-hidden">
      <div className="landing-veil" aria-hidden />

      <div className="landing-bg pointer-events-none fixed inset-0">
        <VideoBackground src={BACKGROUND_VIDEO} />
      </div>

      <header className="reveal fixed inset-x-0 top-0 z-40 px-4 pt-5 md:px-8" style={delay(0)}>
        <nav className="glass mx-auto flex h-[68px] max-w-[1400px] items-center justify-between rounded-full px-4 md:px-7" aria-label="Main">
          <Link to="/" className="flex items-center gap-2.5 text-[16px] font-semibold tracking-[0.14em] md:text-[19px] md:tracking-[0.18em]">
            <BrandLogo className="size-9 rounded-full ring-1 ring-white/30" />
            AGENT-P
          </Link>
          <div className="hidden items-center gap-1 md:flex">
            <NavItem to="#how">How it works</NavItem>
            <NavItem to="#trust">Why trust it</NavItem>
            <NavItem to="/dashboard">Dashboard</NavItem>
            <NavItem to="/tasks/new">Import repo</NavItem>
            <NavItem to="https://github.com/AayushAryan007/Agent-P" external>
              GitHub
            </NavItem>
          </div>
          <Link
            to="/dashboard"
            className="cta-pill shrink-0 rounded-full border border-white/70 bg-white px-4 py-2 text-[13px] font-medium text-[#04081f] md:px-5 md:py-2.5 md:text-[14px]"
          >
            Open dashboard
          </Link>
        </nav>
      </header>

      <main className="relative z-10">
        <section className="mx-auto grid min-h-screen max-w-[1400px] grid-cols-1 items-center gap-12 px-5 pb-16 pt-32 md:px-12 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div>
            <p className="reveal mb-6 flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.2em] text-cyan/90 md:text-[12px] md:tracking-[0.32em]" style={delay(1)}>
              <span className="inline-block h-px w-10 shrink-0 bg-cyan/60" />
              AI agent execution &amp; observability
            </p>
            <h1 className="reveal text-[clamp(44px,7.2vw,104px)] font-normal leading-[0.98] tracking-[-0.03em]" style={delay(2)}>
              AGENT-P — agents
              <br />
              you can <span className="bg-gradient-to-r from-white via-[#a9c4ff] to-[#5fd8ff] bg-clip-text text-transparent">watch</span>
            </h1>
            <p className="reveal mt-7 text-[clamp(15px,1.6vw,22px)] font-medium uppercase tracking-[0.06em] text-[var(--l-mute)]" style={delay(3)}>
              Live graphs. Human approval. Verified fixes.
            </p>
            <p className="reveal mt-5 max-w-[560px] text-[16px] leading-relaxed text-[var(--l-mute)]" style={delay(4)}>
              Give it a slow endpoint in a Python repo. Watch a coordinator and specialised agents investigate, propose a
              patch, wait for your approval, and prove the fix with real tests and benchmarks in an isolated sandbox.
            </p>
            <div className="reveal mt-10 flex flex-wrap items-center gap-4" style={delay(5)}>
              <Link to="/tasks/new" className="group flex items-center gap-1">
                <span className="cta-pill rounded-full border border-white/70 px-7 py-3.5 text-[15px]">Import a repository</span>
                <span className="cta-arrow grid size-[50px] place-items-center rounded-full border border-white/70">
                  <ArrowUpRight className="size-5" aria-hidden />
                </span>
              </Link>
              <Link
                to="/runs"
                className="flex items-center gap-2 rounded-full px-5 py-3.5 text-[15px] text-[var(--l-mute)] transition-colors hover:text-white"
              >
                <PlayCircle className="size-5" aria-hidden /> Replay a recorded run
              </Link>
            </div>
          </div>

          <aside className="flex flex-col gap-5" aria-label="Live platform metrics">
            <StatCard d={0} value={live ? (m?.runs_total ?? 0) : null} caption="agent runs executed in the last 30 days" />
            <StatCard
              d={1}
              value={live && m?.success_rate != null ? m.success_rate * 100 : null}
              suffix="%"
              caption="of finished runs completed successfully"
            />
            <StatCard d={2} value={live ? (m?.verified_runs ?? 0) : null} caption="fixes verified by real tests and benchmarks in the sandbox" />
            <p className="reveal-right flex items-center gap-2 px-2 text-[11px] uppercase tracking-[0.2em] text-[var(--l-mute)]" style={delay(3)}>
              <span className={`size-1.5 rounded-full ${live ? 'animate-pulse bg-green' : 'bg-slate'}`} />
              {live ? 'Live from the AGENT-P API' : 'Connect the API to see live numbers'}
            </p>
          </aside>
        </section>

        <section id="how" className="mx-auto max-w-[1400px] scroll-mt-28 px-6 py-24 md:px-12">
          <div className="scan-line mb-14 w-full" aria-hidden />
          <h2 className="text-[clamp(32px,4vw,56px)] font-normal tracking-[-0.02em]">How it works</h2>
          <p className="mt-3 max-w-[620px] text-[var(--l-mute)]">
            Every step is a persisted, ordered event — the live graph, the replay, and the final report all tell the same story.
          </p>
          <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <div key={title} className="glass rounded-[22px] p-7">
                <div className="flex items-center justify-between">
                  <span className="grid size-11 place-items-center rounded-full bg-white/8 ring-1 ring-white/15">
                    <Icon className="size-5 text-[#9fc0ff]" aria-hidden />
                  </span>
                  <span className="font-mono text-[12px] text-[var(--l-mute)]">0{i + 1}</span>
                </div>
                <h3 className="mt-8 text-[22px] font-medium">{title}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-[var(--l-mute)]">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="trust" className="mx-auto max-w-[1400px] scroll-mt-28 px-6 pb-28 md:px-12">
          <div className="glass grid gap-10 rounded-[28px] p-8 md:grid-cols-3 md:p-12">
            {[
              ['Evidence, not claims', '“Verified” is computed from sandbox exit codes and benchmark output. The model can never upgrade it.'],
              ['Deterministic replay', 'Completed runs replay from stored events at any speed. No model is called again.'],
              ['Sandboxed by design', 'Non-root containers, no network for tests, read-only code, resource limits. Your keys never reach a sandbox.'],
            ].map(([t, b]) => (
              <div key={t}>
                <h3 className="text-[20px] font-medium">{t}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-[var(--l-mute)]">{b}</p>
              </div>
            ))}
          </div>
        </section>

        <footer className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-4 border-t border-white/10 px-6 py-8 text-[13px] text-[var(--l-mute)] md:px-12">
          <span>AGENT-P · open-source AI agent execution &amp; observability</span>
          <span className="flex items-center gap-5">
            <Link to="/dashboard" className="hover:text-white">
              Dashboard
            </Link>
            <a href="https://github.com/AayushAryan007/Agent-P" target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:text-white">
              <GitBranch className="size-4" aria-hidden /> Source
            </a>
          </span>
        </footer>
      </main>
    </div>
  )
}
