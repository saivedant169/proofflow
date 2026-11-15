import type { Currentness } from '../lib/types'

export default function Status({ state, compact = false }: { state: Currentness; compact?: boolean }) {
  const label = state === 'current' ? 'Current' : state === 'stale' ? 'Needs refresh' : 'Evidence unavailable'
  return <span className={`status status-${state} ${compact ? 'status-compact' : ''}`}><i aria-hidden="true" />{label}</span>
}
