export interface FileDiff {
  path: string
  lines: string[]
  additions: number
  deletions: number
}

/** Split a unified diff into files. Content is rendered as text, never as HTML. */
export function parseUnifiedDiff(diff: string): FileDiff[] {
  const files: FileDiff[] = []
  let current: FileDiff | null = null
  for (const line of diff.split('\n')) {
    if (line.startsWith('--- ')) continue
    if (line.startsWith('+++ ')) {
      current = { path: line.slice(4).replace(/^b\//, ''), lines: [], additions: 0, deletions: 0 }
      files.push(current)
      continue
    }
    if (!current) continue
    if (line.startsWith('+')) current.additions++
    else if (line.startsWith('-')) current.deletions++
    current.lines.push(line)
  }
  return files
}
