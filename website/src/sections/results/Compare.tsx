import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { ArrowDownWideNarrow } from 'lucide-react'
import { Source } from '../../components/ui'
import { accounting } from './data'
import { EASE, nf, useReveal } from './parts'

type Row = (typeof accounting.rows)[number]
type Metric = 'correct' | 'tokens' | 'cost'

const MAX = {
  correct: accounting.of,
  tokens: Math.max(...accounting.rows.map(r => r.tokens)),
  cost: Math.max(...accounting.rows.map(r => r.cost)),
}

const METRICS: { id: Metric; title: string; short: string; hint: string }[] = [
  { id: 'correct', title: 'Correct reports', short: 'Correct', hint: 'of 32, higher wins' },
  { id: 'tokens', title: 'Input tokens', short: 'Tokens', hint: 'lower wins' },
  { id: 'cost', title: 'Measured list cost', short: 'List cost', hint: 'lower wins' },
]

const usd = (n: number, d = 2) => '$' + n.toFixed(d)

function value(r: Row, m: Metric) {
  return m === 'correct' ? r.correct : m === 'tokens' ? r.tokens : r.cost
}

export default function Compare() {
  const [sort, setSort] = useState<Metric | null>(null)
  const { ref, show, reduce } = useReveal<HTMLDivElement>(0.25)

  const rows = useMemo(() => {
    if (!sort) return [...accounting.rows]
    return [...accounting.rows].sort((a, b) =>
      sort === 'correct' ? b.correct - a.correct || a.cost - b.cost : value(a, sort) - value(b, sort))
  }, [sort])

  return (
    <div className="rs-cmp" ref={ref}>
      <div className="rs-cmp-head">
        <h3 className="rs-cmp-title">Six approaches, one model</h3>
        <p className="rs-cmp-sort" id="rs-sort-label">
          <ArrowDownWideNarrow size={16} strokeWidth={2} aria-hidden /> Sort by a column
        </p>
      </div>

      <div className="rs-cmp-table" role="table" aria-label="Six approaches compared: correct reports out of 32, input tokens and measured list cost, actual-model study">
        <div className="rs-cmp-row rs-cmp-colhead" role="row">
          <span role="columnheader" className="rs-cmp-name-h">Approach</span>
          {METRICS.map(m => (
            <span role="columnheader" key={m.id} aria-sort={sort === m.id ? (m.id === 'correct' ? 'descending' : 'ascending') : 'none'}>
              <button
                type="button"
                className={`rs-cmp-colbtn${sort === m.id ? ' is-on' : ''}`}
                aria-pressed={sort === m.id}
                onClick={() => setSort(sort === m.id ? null : m.id)}
              >
                <span className="rs-cmp-coltitle">{m.title}</span>
                <span className="rs-cmp-colhint">{m.hint}</span>
              </button>
            </span>
          ))}
        </div>

        {rows.map((r, i) => {
          const cls = `rs-cmp-row rs-cmp-data${'highlight' in r ? ' is-hl' : ''}${'ablation' in r ? ' is-ablation' : ''}`
          return (
            <motion.div layout={!reduce} transition={{ duration: 0.5, ease: EASE }} key={r.key} className={cls} role="row" tabIndex={0}
              aria-label={`${r.label}, ${r.sub}: ${r.correct} of 32 correct, ${nf(r.tokens)} input tokens, ${usd(r.cost, 4)} list cost`}>
              <span role="rowheader" className="rs-cmp-name">
                <span className="rs-cmp-label">{r.label}</span>
                <span className="rs-cmp-sub">{r.sub}</span>
              </span>
              {METRICS.map(m => {
                const v = value(r, m.id)
                const w = show ? `${(v / MAX[m.id]) * 100}%` : '0%'
                return (
                  <span role="cell" key={m.id} className={`rs-cmp-cell is-${m.id}`}>
                    <span className="rs-cmp-metric" aria-hidden="true">{m.short}</span>
                    <span className="rs-cmp-track" aria-hidden="true">
                      <motion.span
                        className="rs-cmp-bar"
                        initial={false}
                        animate={{ width: w }}
                        transition={{ duration: reduce ? 0 : 1, ease: EASE, delay: reduce ? 0 : 0.15 + i * 0.08 + (m.id === 'correct' ? 0 : m.id === 'tokens' ? 0.18 : 0.36) }}
                      />
                    </span>
                    <span className="rs-cmp-val figure">
                      {m.id === 'correct' && <>{r.correct}<span className="rs-cmp-of">/32</span></>}
                      {m.id === 'tokens' && nf(r.tokens)}
                      {m.id === 'cost' && <>
                        <span className="rs-cmp-cost-short">{usd(r.cost)}</span>
                        <span className="rs-cmp-cost-exact">{usd(r.cost, 4)}</span>
                      </>}
                    </span>
                  </span>
                )
              })}
            </motion.div>
          )
        })}
      </div>

      <div className="rs-cmp-foot">
        <span className="rs-cmp-legend"><span className="rs-sw is-hl" />ProofFlow</span>
        <span className="rs-cmp-legend"><span className="rs-sw" />Today’s approaches</span>
        <span className="rs-cmp-legend"><span className="rs-sw is-ablation" />Ablation</span>
        <Source path={accounting.source} label="docs/MODEL_COMPARISON_RESULTS.md, Provider accounting" />
      </div>
    </div>
  )
}
