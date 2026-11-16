import { useEffect, useState, type CSSProperties } from 'react'
import { ARMS, OF, arm, derived, int, usd2, type ArmId } from './data'

/**
 * Hero signature visual: accuracy against input for every arm of the real-model study. ProofFlow lands
 * top-left: full-context correctness at the retrieval baselines' budget. Switch the axis to measured list
 * cost and the exact-flat ablation slides left (its cache reads were cheaper), which is the honest caveat.
 * Data: ./data.ts (docs/MODEL_COMPARISON_RESULTS.md).
 */

type Mode = 'tokens' | 'cost'

const AXIS: Record<Mode, { max: number; ticks: number[]; tick: (v: number) => string; title: string; value: (id: ArmId) => number }> = {
  tokens: {
    max: 240_000,
    ticks: [0, 80_000, 160_000, 240_000],
    tick: v => (v === 0 ? '0' : `${v / 1000}k`),
    title: 'Input tokens',
    value: id => arm(id).inputTokens,
  },
  cost: {
    max: 4,
    ticks: [0, 1, 2, 3, 4],
    tick: v => `$${v}`,
    title: 'Measured list cost',
    value: id => arm(id).costUsd,
  },
}

const Y_TICKS = [0, 8, 16, 24, 32]

/** Where each point's label sits, relative to its dot. */
const PLACE: Record<ArmId, string> = {
  graph: 'above',
  exact: 'below',
  hybrid: 'right',
  bm25: 'right',
  dense: 'right',
  full: 'above-end',
}

const ORDER: ArmId[] = ['dense', 'bm25', 'hybrid', 'full', 'exact', 'graph']

export default function Plot() {
  const [mode, setMode] = useState<Mode>('tokens')
  const [active, setActive] = useState<ArmId>('graph')
  const [ready, setReady] = useState(false)

  // Points rise into place after first paint.
  useEffect(() => {
    const r = requestAnimationFrame(() => requestAnimationFrame(() => setReady(true)))
    return () => cancelAnimationFrame(r)
  }, [])

  const ax = AXIS[mode]
  const x = (id: ArmId) => (ax.value(id) / ax.max) * 100
  const y = (id: ArmId) => (arm(id).correct / OF) * 100
  const a = arm(active)
  const gx = x('graph')
  const fx = x('full')

  return (
    <figure className="plot" data-mode={mode} data-ready={ready ? 'true' : undefined} aria-labelledby="plot-title">
      <div className="plot-head">
        <p className="plot-title" id="plot-title">Affected reports right, of {OF}</p>
        <div className="plot-switch" role="group" aria-label="Horizontal axis">
          {(['tokens', 'cost'] as Mode[]).map(m => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}>
              {m === 'tokens' ? 'Tokens' : 'Cost'}
            </button>
          ))}
        </div>
      </div>

      <div className="plot-area">
        <div className="plot-inner">
          {Y_TICKS.map(t => (
            <span key={t} className="plot-grid" style={{ '--y': `${(t / OF) * 100}%` } as CSSProperties} aria-hidden>
              <span className="plot-ytick figure">{t}</span>
            </span>
          ))}
          {ax.ticks.map(t => (
            <span key={`${mode}-${t}`} className="plot-xtick" style={{ '--x': `${(t / ax.max) * 100}%` } as CSSProperties} aria-hidden>
              {ax.tick(t)}
            </span>
          ))}
          <span className="plot-xtitle" aria-hidden>{ax.title}</span>

          {/* Same answers as full context, for far less: the horizontal gap. */}
          <span className="plot-span" style={{ '--x0': `${gx}%`, '--x1': `${fx}%` } as CSSProperties} aria-hidden>
            <span className="plot-span-text figure">
              {mode === 'tokens' ? `${int(derived.tokensSaved)} fewer tokens` : `${Math.round(derived.costLowerPct)}% lower cost`}
            </span>
          </span>

          {/* Same budget as vector RAG, far more right: the vertical gap. */}
          <span className="plot-rise" style={{ '--x': `${gx}%`, '--y0': `${y('dense')}%` } as CSSProperties} aria-hidden>
            <span className="plot-rise-text">
              <span className="figure">{derived.vsVector.toFixed(1)}<span className="times">×</span></span>
              <span>vs vector RAG</span>
            </span>
          </span>

          <ul className="plot-points" aria-label="Study arms">
            {ORDER.map((id, i) => (
              <li key={id} className={`plot-pt pt-${id}`} data-place={id === 'exact' && mode === 'tokens' ? 'below-start' : PLACE[id]} data-active={active === id ? 'true' : undefined}
                style={{ '--x': `${x(id)}%`, '--y': `${y(id)}%`, '--i': i } as CSSProperties}>
                <button type="button" className="plot-dot" onMouseEnter={() => setActive(id)} onFocus={() => setActive(id)}
                  onClick={() => setActive(id)}
                  aria-label={`${arm(id).name}: ${arm(id).correct} of ${OF} right, ${int(arm(id).inputTokens)} input tokens, ${usd2(arm(id).costUsd)} list cost`}>
                  <span className="plot-dot-core" aria-hidden />
                </button>
                <span className="plot-label" aria-hidden>{arm(id).label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="plot-readout" aria-live="polite">
        <span className="plot-readout-name">{a.name}</span>
        <span className="plot-readout-stats">
          <span><b className="figure">{a.correct}/{OF}</b> right</span>
          <span><b className="figure">{int(a.inputTokens)}</b> input tokens</span>
          <span><b className="figure">{usd2(a.costUsd)}</b> list cost</span>
        </span>
      </p>
      <figcaption className="sr-only">
        Real-model study, eight cases, one sample each. {ARMS.map(r => `${r.name}: ${r.correct} of ${OF}`).join('; ')}.
      </figcaption>
    </figure>
  )
}
