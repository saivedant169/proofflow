import { useId, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { Source } from '../../components/ui'
import { accounting } from './data'
import { EASE } from './parts'

const D = accounting.derived
const MIN = 100
const MAX = 100_000
const STEPS = 300

/** Slider position (0..STEPS) to refreshes per day on a log scale, rounded to two significant digits. */
function toCount(pos: number) {
  const raw = MIN * Math.pow(MAX / MIN, pos / STEPS)
  const mag = Math.pow(10, Math.floor(Math.log10(raw)) - 1)
  return Math.min(MAX, Math.max(MIN, Math.round(raw / mag) * mag))
}
function toPos(count: number) {
  return Math.round((Math.log(count / MIN) / Math.log(MAX / MIN)) * STEPS)
}

const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const money = (n: number) =>
  n >= 100_000
    ? '$' + compact.format(n)
    : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: n >= 100 ? 0 : 2, maximumFractionDigits: n >= 100 ? 0 : 2 })

export default function Calculator() {
  const [pos, setPos] = useState(toPos(1000))
  const reduce = !!useReducedMotion()
  const id = useId()
  const n = toCount(pos)

  const tokens = n * D.perCaseTokensSaved
  const dollars = n * D.perCaseCostSaved
  const wrong = (n * D.vectorMissed) / accounting.cases

  const outs = [
    { k: 'tokens', value: compact.format(tokens), label: 'input tokens saved daily', vs: 'vs full context' },
    { k: 'cost', value: money(dollars), label: 'list cost saved daily', vs: 'vs full context' },
    { k: 'wrong', value: int.format(wrong), label: 'stale reports avoided daily', vs: 'vs vector RAG' },
  ]

  return (
    <div className="rs-calc">
      <div className="rs-calc-head">
        <h3 className="rs-calc-title">Savings at your volume</h3>
        <p className="rs-calc-note">Illustrative, at this study’s measured list cost.</p>
      </div>

      <div className="rs-calc-input">
        <label htmlFor={id} className="rs-calc-label">Refreshes per day</label>
        <output htmlFor={id} className="rs-calc-n figure">{int.format(n)}</output>
        <input
          id={id}
          type="range"
          min={0}
          max={STEPS}
          step={1}
          value={pos}
          onChange={e => setPos(Number(e.target.value))}
          aria-valuetext={`${int.format(n)} refreshes per day`}
          className="rs-range"
          style={{ ['--fill' as string]: `${(pos / STEPS) * 100}%` }}
        />
        <div className="rs-range-scale" aria-hidden="true">
          <span>100</span><span>1K</span><span>10K</span><span>100K</span>
        </div>
      </div>

      <ul className="rs-calc-outs" aria-live="polite">
        {outs.map(o => (
          <li key={o.k} className={`rs-calc-out is-${o.k}`}>
            <motion.span
              key={o.value}
              className="rs-calc-val figure"
              initial={reduce ? false : { opacity: 0.4, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduce ? 0 : 0.22, ease: EASE }}
            >
              {o.value}
            </motion.span>
            <span className="rs-calc-lab">{o.label}</span>
            <span className="rs-calc-vs">{o.vs}</span>
          </li>
        ))}
      </ul>

      <p className="rs-calc-basis">
        <span>Per refresh, measured: {int.format(D.perCaseTokensSaved)} tokens and ${D.perCaseCostSaved.toFixed(4)} saved; vector RAG missed {D.vectorMissed} of 32 reports over {accounting.cases} cases.</span>
        <Source path={accounting.source} />
      </p>
    </div>
  )
}
