import { motion } from 'motion/react'
import { Source } from '../../components/ui'
import { retail } from './data'
import { CountUp, EASE, nf, useReveal } from './parts'

const LABELS = ['ProofFlow', 'Exact-flat', 'Hybrid', 'BM25 keyword', 'Vector RAG']

/** Retail benchmark: evidence tokens as a tape, plus correctness at the same allowance. */
export default function Meter() {
  const { ref, show, reduce } = useReveal<HTMLDivElement>(0.35)
  const t = { duration: reduce ? 0 : 1.4, ease: EASE, delay: reduce ? 0 : 0.2 }
  const share = retail.ratioValue

  return (
    <div className="rs-meter" ref={ref}>
      <div className="rs-meter-head">
        <p className="rs-meter-big figure">
          <span className="rs-meter-num"><CountUp to={69.41} decimals={2} suffix="%" start={show} duration={1.6} /></span>
          <span className="rs-meter-big-label">fewer evidence tokens<span className="rs-meter-ctx">Retail benchmark, no LLM</span></span>
        </p>
      </div>

      <div
        className="rs-tape-wrap"
        role="img"
        aria-label={`ProofFlow read ${nf(retail.graphTokens)} evidence tokens versus ${nf(retail.fullTokens)} for full context across ten cases: ${retail.ratioPct} of full context, ${retail.fewerPct} fewer.`}
      >
        <div className="rs-tape-labels" aria-hidden="true">
          <motion.span className="rs-tape-mark is-part" initial={false} animate={{ left: show ? `${share}%` : '0%' }} transition={t}>
            <span className="rs-tape-name">ProofFlow</span>
            <span className="figure">{nf(retail.graphTokens)}</span>
          </motion.span>
          <span className="rs-tape-mark is-full">
            <span className="rs-tape-name">Full context</span>
            <span className="figure">{nf(retail.fullTokens)}</span>
          </span>
        </div>
        <div className="rs-tape" aria-hidden="true">
          <motion.span className="rs-tape-fill" initial={false} animate={{ width: show ? `${share}%` : '0%' }} transition={t} />
          <motion.span className="rs-tape-gap" initial={false} animate={{ left: show ? `${share}%` : '0%', opacity: show ? 1 : 0 }} transition={t}>
            <span className="rs-tape-saved figure">{nf(retail.fullTokens - retail.graphTokens)} tokens saved</span>
          </motion.span>
        </div>
      </div>

      <div className="rs-allow">
        <p className="rs-allow-title">Same allowance, correct of 38</p>
        <ul className="rs-allow-list">
          {retail.rows.map((r, i) => (
            <li key={r.label} className={'highlight' in r ? 'is-hl' : undefined}>
              <span className="rs-allow-val figure">{r.value}<span className="rs-cmp-of">/38</span></span>
              <span className="rs-allow-track" aria-hidden="true">
                <motion.span className="rs-allow-bar" initial={false} animate={{ width: show ? `${(r.value / retail.of) * 100}%` : '0%' }}
                  transition={{ duration: reduce ? 0 : 0.9, ease: EASE, delay: reduce ? 0 : 0.5 + i * 0.08 }} />
              </span>
              <span className="rs-allow-label">{LABELS[i]}</span>
            </li>
          ))}
        </ul>
        <Source path={retail.source} />
      </div>
    </div>
  )
}
