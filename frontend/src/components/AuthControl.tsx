import { KeyRound, LogOut } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { ApiError } from '@/api/client'
import { useMe, useSignIn, useSignOut } from '@/api/queries'
import { Button } from './ui'

/** Viewer/operator chip with an inline sign-in form (ADR-0004: single admin token). */
export function AuthControl() {
  const me = useMe()
  const signIn = useSignIn()
  const signOut = useSignOut()
  const [open, setOpen] = useState(false)
  const [token, setToken] = useState('')
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (panel.current && !panel.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!me.data) return null

  if (me.data.role === 'operator') {
    return (
      <span className="flex items-center gap-1 rounded-full border border-green/30 bg-green/10 py-0.5 pl-2.5 pr-1 text-[11px] text-green">
        Operator
        <button
          type="button"
          aria-label="Sign out"
          title="Sign out"
          onClick={() => signOut.mutate()}
          className="grid size-5 place-items-center rounded-full text-fg-3 hover:bg-surface-3 hover:text-fg"
        >
          <LogOut className="size-3" />
        </button>
      </span>
    )
  }

  const error = signIn.error instanceof ApiError ? signIn.error.message : null
  return (
    <div className="relative" ref={panel}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-[11px] text-fg-2 hover:border-border-strong hover:text-fg"
      >
        Viewer · Sign in
      </button>
      {open && (
        <form
          className="absolute right-0 top-8 z-50 w-72 space-y-3 rounded-panel border border-border bg-surface-2 p-4 shadow-2xl"
          onSubmit={(e) => {
            e.preventDefault()
            signIn.mutate(token, {
              onSuccess: () => {
                setOpen(false)
                setToken('')
              },
            })
          }}
        >
          <label className="block">
            <span className="mb-1.5 block text-caps font-semibold uppercase text-fg-2">Operator token</span>
            <input
              type="password"
              autoFocus
              autoComplete="current-password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full rounded-control border border-border bg-bg px-3 py-2 font-mono text-fg focus:border-blue focus:outline-none"
            />
          </label>
          {error && <p className="text-[12px] text-red">{error}</p>}
          <Button type="submit" variant="primary" icon={KeyRound} className="w-full" loading={signIn.isPending} disabled={!token}>
            Sign in
          </Button>
          <p className="text-[11px] text-fg-3">Viewers can browse and replay public runs without signing in.</p>
        </form>
      )}
    </div>
  )
}
