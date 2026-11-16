import { Source, StateTag } from '../../components/ui'

/** The three results of ProofFlowRuntime.currentness() and the reason codes it records. */
const STATES = [
  {
    state: 'current' as const,
    text: 'Every source and tool version it depends on is still the latest, and every stored record checks out. The value is served.',
    reasons: [],
  },
  {
    state: 'stale' as const,
    text: 'A source or tool version it depends on was replaced. The saved value is withheld until refresh recomputes it.',
    reasons: ['version_changed', 'implementation_changed'],
  },
  {
    state: 'unknown' as const,
    text: 'Evidence is missing or corrupt, a source was removed, or the recorded lineage is incomplete. It fails closed: the value is never served and refresh will not guess. Unknown wins over stale.',
    reasons: ['missing_manifest_record', 'missing_or_corrupt_content', 'source_removed', 'incomplete_graph_lineage'],
  },
]

export function StateLegend() {
  return (
    <div className="how-states">
      <h3 className="how-states-title">Three states, checked before a value is served</h3>
      <dl className="how-state-list">
        {STATES.map(s => (
          <div key={s.state} className={`how-state how-state--${s.state}`}>
            <dt>
              <span className="how-swatch" aria-hidden />
              <StateTag state={s.state} />
            </dt>
            <dd>
              <p>{s.text}</p>
              {s.reasons.length > 0 && (
                <p className="how-reasons">
                  <span className="sr-only">Recorded reasons: </span>
                  {s.reasons.map(r => <code key={r}>{r}</code>)}
                </p>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <p className="how-source-row">
        <Source path="proofflow/runtime.py" label="proofflow/runtime.py (currentness)" />
      </p>
    </div>
  )
}
