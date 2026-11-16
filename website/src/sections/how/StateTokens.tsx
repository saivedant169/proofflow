import { Tip } from './Tip'

/** The three results of ProofFlowRuntime.currentness() and the reason codes it records (proofflow/runtime.py). */
const STATES = [
  {
    state: 'current' as const,
    word: 'Current',
    tip: 'Every source and tool version it depends on is still the latest, and every record checks out. Served.',
    reasons: [],
  },
  {
    state: 'stale' as const,
    word: 'Stale',
    tip: 'A source or tool version it depends on was replaced. Withheld until refresh recomputes it.',
    reasons: ['version_changed', 'implementation_changed'],
  },
  {
    state: 'unknown' as const,
    word: 'Unknown',
    tip: 'Evidence missing or corrupt, a source removed, or lineage incomplete. Fails closed: never served, never guessed. Unknown wins over stale.',
    reasons: ['missing_manifest_record', 'missing_or_corrupt_content', 'source_removed', 'incomplete_graph_lineage'],
  },
]

export type TokenState = (typeof STATES)[number]['state']

export function StateTokens({ live }: { live: ReadonlySet<TokenState> }) {
  return (
    <ul className="how-tokens" aria-label="Currentness states">
      {STATES.map((s, i) => (
        <li key={s.state}>
          <Tip className={`how-token how-token--${s.state}`} data-live={live.has(s.state) || undefined}
            align={i === 0 ? 'start' : i === STATES.length - 1 ? 'end' : 'center'}
            tip={<>{s.tip}{s.reasons.length > 0 && <><br />{s.reasons.map(r => <code key={r}>{r}</code>)}</>}</>}>
            <span className="how-token-mark" aria-hidden />
            {s.word}
          </Tip>
        </li>
      ))}
    </ul>
  )
}
