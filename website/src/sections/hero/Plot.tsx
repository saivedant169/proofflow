import { useEffect, useState, type CSSProperties } from 'react'
import { OF, arm, int, usd2, type ArmId } from './data'

/**
 * Hero signature visual, two single-measure charts from the real-model study.
 * 1. Versus full context (same 32/32 right): input tokens and list cost as stacked lanes. ProofFlow's bar
 *    is solid; the dashed run out to full context's length is the saving, so both savings read at once.
 * 2. Versus retrieval at the same ~76k-token budget: affected reports right, of 32.
 * Exact-flat's cheaper cache-read cost is disclosed in the note. Data: ./data.ts (docs/MODEL_COMPARISON_RESULTS.md).
 */

const graph = arm('graph')
const full = arm('full')

type Lane = { key: string; name: string; pf: number; fc: number; pfText: string; fcText: string; saved: string }

const LANES: Lane[] = [
  {
    key: 'tokens',
    name: 'Input tokens',
    pf: graph.inputTokens,
    fc: full.inputTokens,
    pfText: int(graph.inputTokens),
    fcText: int(full.inputTokens),
    saved: `${int(full.inputTokens - graph.inputTokens)} fewer`,
  },
  {
    key: 'cost',
    name: 'List cost',
    pf: graph.costUsd,
    fc: full.costUsd,
    pfText: usd2(graph.costUsd),
    fcText: usd2(full.costUsd),
    saved: `${usd2(full.costUsd - graph.costUsd)} less`,
  },
]

const ACCURACY: ArmId[] = ['graph', 'full', 'exact', 'hybrid', 'bm25', 'dense']

export default function Plot() {
  const [ready, setReady] = useState(false)

  // Bars grow into place after first paint.
  useEffect(() => {
    const r = requestAnimationFrame(() => requestAnimationFrame(() => setReady(true)))
    return () => cancelAnimationFrame(r)
  }, [])

  return (
    <figure className="plot" data-ready={ready ? 'true' : undefined} aria-labelledby="plot-title">
      <p className="plot-title" id="plot-title">
        Versus full context <span className="plot-title-aside">both {OF}/{OF} right</span>
      </p>

      <div className="plot-lanes">
        {LANES.map((l, i) => {
          const w = (l.pf / l.fc) * 100
          const pct = Math.round(100 - w)
          return (
            <div key={l.key} className="lane" style={{ '--w': `${w}%`, '--i': i } as CSSProperties}>
              <div className="lane-head">
                <span className="lane-name">{l.name}</span>
                <span className="lane-save"><b className="figure">−{pct}%</b>{l.saved}</span>
              </div>
              <div className="lane-track" role="img"
                aria-label={`${l.name}: ProofFlow ${l.pfText}, full context ${l.fcText}, ${pct}% lower`}>
                <span className="lane-bar"><span className="lane-bar-text figure">{l.pfText}</span></span>
                <span className="lane-ghost" aria-hidden />
              </div>
              <div className="lane-scale" aria-hidden>
                <span>ProofFlow</span>
                <span>Full context <span className="figure">{l.fcText}</span></span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="plot-acc">
        <p className="plot-title">
          Versus retrieval <span className="plot-title-aside">right, of {OF}, at the same ~76k-token budget</span>
        </p>
        <ul className="acc-rows">
          {ACCURACY.map((id, i) => (
            <li key={id} className={`acc-row acc-${id}`} style={{ '--w': `${(arm(id).correct / OF) * 100}%`, '--i': i + 2 } as CSSProperties}>
              <span className="acc-name">{arm(id).label}</span>
              <span className="acc-track" aria-hidden><span className="acc-bar" /></span>
              <span className="acc-val figure">{arm(id).correct}<span className="sr-only"> of {OF}</span></span>
            </li>
          ))}
        </ul>
      </div>

      <p className="plot-note">
        Real-model study: eight fresh cases, one sample each. List cost depends on cache treatment; the exact-flat
        ablation’s cache reads cost {usd2(arm('exact').costUsd)}.
      </p>
    </figure>
  )
}
