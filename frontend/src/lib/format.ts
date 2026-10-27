export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)} s`
  const m = Math.floor(s / 60)
  return `${m}m ${Math.round(s % 60)}s`
}

export function durationBetween(start: string | null, end: string | null, now = Date.now()): number | null {
  if (!start) return null
  const a = Date.parse(start)
  const b = end ? Date.parse(end) : now
  return Number.isFinite(a) && Number.isFinite(b) ? Math.max(0, b - a) : null
}

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })

export function formatTokens(n: number | null | undefined): string {
  return n == null ? '—' : compact.format(n)
}

export function formatPercent(ratio: number | null | undefined): string {
  return ratio == null ? '—' : `${(ratio * 100).toFixed(1)}%`
}

export function formatClock(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleTimeString('en-GB', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0')
}

export function formatRelative(iso: string | null, now = Date.now()): string {
  if (!iso) return '—'
  const diff = (now - Date.parse(iso)) / 1000
  if (!Number.isFinite(diff)) return '—'
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
