import { useRef, type ReactNode } from 'react'
import { motion, useInView, useReducedMotion } from 'motion/react'
import type { BarRow } from './data'

const EASE = [0.22, 1, 0.36, 1] as const
const nf = (n: number) => n.toLocaleString('en-US')

/** Reveal once when the figure enters view. With reduced motion, show the end state at once. */
function useReveal<T extends Element>() {
  const ref = useRef<T>(null)
  const inView = useInView(ref, { once: true, amount: 0.35 })
  const reduce = !!useReducedMotion()
  return { ref, show: inView || reduce, reduce }
}

const pct = (v: number, max: number) => `${(v / max) * 100}%`

/* ------------------------------------------------------------------ */
/* Horizontal bar chart: count out of N per method                     */
/* ------------------------------------------------------------------ */

export function BarChart({ rows, max, ticks, title, unit, tableCaption, extraColumn }: {
  rows: readonly (BarRow & { extra?: string })[]
  max: number
  ticks: readonly number[]
  title: ReactNode
  unit: string
  tableCaption: string
  extraColumn?: string
}) {
  const { ref, show, reduce } = useReveal<HTMLDivElement>()
  return (
    <div className="rs-chart" ref={ref}>
      <p className="rs-chart-title">{title}</p>
      <div className="rs-bars" aria-hidden="true">
        {rows.map((r, i) => (
          <div key={r.label} className={`rs-row${r.highlight ? ' is-hl' : ''}${r.reference ? ' is-ref' : ''}`}>
            <span className="rs-row-label">{r.label}</span>
            <div className="rs-track">
              <motion.span
                className="rs-bar"
                initial={false}
                animate={{ width: show ? pct(r.value, max) : '0%' }}
                transition={{ duration: reduce ? 0 : 0.8, ease: EASE, delay: reduce ? 0 : i * 0.07 }}
              />
              <motion.span
                className="rs-value figure"
                style={{ left: pct(r.value, max) }}
                initial={false}
                animate={{ opacity: show ? 1 : 0 }}
                transition={{ duration: reduce ? 0 : 0.3, delay: reduce ? 0 : 0.55 + i * 0.07 }}
              >
                {r.value}/{max}
              </motion.span>
            </div>
          </div>
        ))}
        <div className="rs-row rs-axis">
          <span className="rs-row-label rs-axis-unit">{unit}</span>
          <div className="rs-track">
            {ticks.map(t => (
              <span key={t} className="rs-tick figure" style={{ left: pct(t, max) }}>{t}</span>
            ))}
          </div>
        </div>
      </div>
      <div className="sr-only"><table>
        <caption>{tableCaption}</caption>
        <thead>
          <tr><th scope="col">Method</th><th scope="col">{unit}</th>{extraColumn && <th scope="col">{extraColumn}</th>}</tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.label}><th scope="row">{r.label}</th><td>{r.value} of {max}</td>{extraColumn && <td>{r.extra}</td>}</tr>
          ))}
        </tbody>
      </table></div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Proportional token comparison: ProofFlow as a share of full context */
/* ------------------------------------------------------------------ */

export function ShareBars({ title, fullLabel, full, part, partLabel, share, shareValue, unit, summary }: {
  title: ReactNode
  fullLabel: string
  full: number
  partLabel: string
  part: number
  share: string
  shareValue: number
  unit: string
  summary: string
}) {
  const { ref, show, reduce } = useReveal<HTMLDivElement>()
  return (
    <div className="rs-chart rs-share" ref={ref}>
      <p className="rs-chart-title">{title}</p>
      <p className="sr-only">{summary}</p>
      <div className="rs-share-rows" aria-hidden="true">
        <div className="rs-share-row">
          <div className="rs-share-meta"><span>{fullLabel}</span><span className="figure">{nf(full)} {unit}</span></div>
          <div className="rs-share-track">
            <motion.span
              className="rs-share-bar"
              initial={false}
              animate={{ width: show ? '100%' : '0%' }}
              transition={{ duration: reduce ? 0 : 0.8, ease: EASE }}
            />
          </div>
        </div>
        <div className="rs-share-row is-hl">
          <div className="rs-share-meta"><span>{partLabel}</span><span className="figure">{nf(part)} {unit}</span></div>
          <div className="rs-share-track">
            <motion.span
              className="rs-share-bar"
              initial={false}
              animate={{ width: show ? `${shareValue}%` : '0%' }}
              transition={{ duration: reduce ? 0 : 0.8, ease: EASE, delay: reduce ? 0 : 0.15 }}
            />
            <motion.span
              className="rs-share-pct figure"
              style={{ left: `${shareValue}%` }}
              initial={false}
              animate={{ opacity: show ? 1 : 0 }}
              transition={{ duration: reduce ? 0 : 0.3, delay: reduce ? 0 : 0.8 }}
            >
              {share}
            </motion.span>
          </div>
        </div>
        <div className="rs-share-scale"><span className="figure">0</span><span>100% of {fullLabel.toLowerCase()}</span></div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Retail comparator table with an inline bar per row                  */
/* ------------------------------------------------------------------ */

export function RetailTable({ rows, of, caption }: {
  rows: readonly (BarRow & { recall: string; endstates: string })[]
  of: number
  caption: string
}) {
  const { ref, show, reduce } = useReveal<HTMLDivElement>()
  return (
    <div className="rs-chart rs-table-wrap scroll-thin" ref={ref}>
      <table className="rs-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Method</th>
            <th scope="col">Fresh affected reports, of {of}</th>
            <th scope="col" className="num">Mean affected-set recall</th>
            <th scope="col" className="num">Correct endstate cases</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.label} className={r.highlight ? 'is-hl' : undefined}>
              <th scope="row">{r.label}</th>
              <td>
                <div className="rs-cell-bar">
                  <span className="rs-mini-track" aria-hidden="true">
                    <motion.span
                      className="rs-bar"
                      initial={false}
                      animate={{ width: show ? pct(r.value, of) : '0%' }}
                      transition={{ duration: reduce ? 0 : 0.8, ease: EASE, delay: reduce ? 0 : i * 0.07 }}
                    />
                  </span>
                  <span className="figure rs-cell-value">{r.value}/{of}</span>
                </div>
              </td>
              <td className="num figure">{r.recall}</td>
              <td className="num figure">{r.endstates}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Dumbbell: fresh reports at two receipt-token caps                    */
/* ------------------------------------------------------------------ */

export function Dumbbell({ rows, max, low, high, uncapped, ticks, caption }: {
  rows: readonly { label: string; low: number; high: number; highlight?: boolean }[]
  max: number
  low: string
  high: string
  uncapped: number
  ticks: readonly number[]
  caption: string
}) {
  const { ref, show, reduce } = useReveal<HTMLDivElement>()
  const t = (d: number) => ({ duration: reduce ? 0 : 0.7, ease: EASE, delay: reduce ? 0 : d })
  return (
    <div className="rs-chart rs-dumbbell" ref={ref}>
      <ul className="rs-legend" aria-hidden="true">
        <li><span className="rs-key rs-key-low" />{low} receipt tokens</li>
        <li><span className="rs-key rs-key-high" />{high} receipt tokens</li>
        <li><span className="rs-key rs-key-ref" />Uncapped reference, {uncapped}/{max}</li>
      </ul>
      <div className="rs-bars rs-db" aria-hidden="true">
        {rows.map((r, i) => (
          <div key={r.label} className={`rs-row${r.highlight ? ' is-hl' : ''}`}>
            <span className="rs-row-label">{r.label}</span>
            <div className="rs-track">
              <motion.span
                className="rs-db-line"
                style={{ left: pct(r.low, max) }}
                initial={false}
                animate={{ width: show ? pct(r.high - r.low, max) : '0%' }}
                transition={t(0.45 + i * 0.08)}
              />
              <motion.span
                className="rs-db-dot is-low"
                initial={false}
                animate={{ left: show ? pct(r.low, max) : '0%', opacity: show ? 1 : 0 }}
                transition={t(i * 0.08)}
              >
                <span className="rs-db-num figure">{r.low}</span>
              </motion.span>
              <motion.span
                className="rs-db-dot is-high"
                initial={false}
                animate={{ left: show ? pct(r.high, max) : pct(r.low, max), opacity: show ? 1 : 0 }}
                transition={t(0.45 + i * 0.08)}
              >
                <span className="rs-db-num figure">{r.high}</span>
              </motion.span>
            </div>
          </div>
        ))}
        <div className="rs-row rs-axis">
          <span className="rs-row-label rs-axis-unit">Fresh reports, of {max}</span>
          <div className="rs-track">
            {ticks.map(v => (
              <span key={v} className="rs-tick figure" style={{ left: pct(v, max) }}>{v}</span>
            ))}
          </div>
        </div>
      </div>
      <div className="sr-only"><table>
        <caption>{caption}</caption>
        <thead>
          <tr><th scope="col">Method</th><th scope="col">At {low} tokens</th><th scope="col">At {high} tokens</th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.label}><th scope="row">{r.label}</th><td>{r.low} of {max}</td><td>{r.high} of {max}</td></tr>
          ))}
          <tr><th scope="row">Full context, uncapped</th><td colSpan={2}>{uncapped} of {max}</td></tr>
        </tbody>
      </table></div>
    </div>
  )
}
