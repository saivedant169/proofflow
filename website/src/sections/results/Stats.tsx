import { useState, type ReactNode } from 'react'
import { Source } from '../../components/ui'
import { accounting, modelStudy } from './data'
import { CountUp, nf, useReveal } from './parts'

type Stat = {
  id: string
  vs: string
  to: number
  decimals?: number
  suffix: string
  label: string
  receipt: ReactNode
  source: string
}

const A = accounting
const usd2 = (n: number) => '$' + n.toFixed(2)

const GROUPS: { label: string; stats: Stat[] }[] = [
  {
    label: 'Versus full context',
    stats: [
      {
        id: 'correct',
        vs: 'vs full context',
        to: 32,
        suffix: '/32',
        label: 'correct reports, same as full',
        receipt: <>Affected reports refreshed across {A.cases} fresh cases, matching full context. {modelStudy.unavailableBlocked} unavailable reports blocked.</>,
        source: A.source,
      },
      {
        id: 'exposure',
        vs: 'vs full context',
        to: modelStudy.exposure.pctValue,
        decimals: 2,
        suffix: '%',
        label: 'of full context’s input',
        receipt: <>{nf(modelStudy.exposure.graph)} of {nf(modelStudy.exposure.full)} provider input tokens, cases M01–M07. Across all eight cases: {nf(A.derived.tokensSaved)} fewer.</>,
        source: A.source,
      },
    ],
  },
  {
    label: 'Versus today’s approaches',
    stats: [
      {
        id: 'cost',
        vs: 'vs full context',
        to: A.derived.costLowerPct,
        suffix: '%',
        label: 'lower measured list cost',
        receipt: <>Derived: {usd2(A.rows[4].cost)} versus {usd2(A.rows[0].cost)} measured list cost for all eight cases. List prices, cache-dependent.</>,
        source: A.source,
      },
      {
        id: 'vector',
        vs: 'vs vector RAG',
        to: 6.4,
        decimals: 1,
        suffix: '×',
        label: 'the correct reports',
        receipt: <>Derived: 32 versus 5 of 32 at the same evidence budget and about the same cost ({usd2(A.rows[4].cost)} versus {usd2(A.rows[1].cost)}).</>,
        source: A.source,
      },
    ],
  },
]

export default function Stats() {
  const { ref, show } = useReveal<HTMLDivElement>(0.4)
  const [open, setOpen] = useState<string | null>(null)

  const stats = GROUPS.flatMap(g => g.stats)
  return (
    <div className="rs-stats" ref={ref}>
      <ul className="rs-stat-list">
        {stats.map((s, i) => {
          const isOpen = open === s.id
          return (
            <li key={s.id} className={`rs-stat${isOpen ? ' is-open' : ''}${s.vs.includes('RAG') ? ' is-alt' : ''}`}
              onMouseLeave={() => { if (isOpen) setOpen(null) }}>
              <span className="rs-stat-vs">{s.vs}</span>
              <button
                type="button"
                className="rs-stat-btn"
                aria-expanded={isOpen}
                aria-describedby={`rs-receipt-${s.id}`}
                onClick={() => setOpen(isOpen ? null : s.id)}
              >
                <span className="rs-stat-num figure">
                  <CountUp to={s.to} decimals={s.decimals} suffix={s.suffix} start={show} delay={i * 0.12} duration={1.6} />
                </span>
                <span className="rs-stat-label">{s.label}<span className="sr-only">, {s.vs}</span></span>
              </button>
              <div className="rs-receipt" id={`rs-receipt-${s.id}`} role="note">
                <p>{s.receipt}</p>
                <Source path={s.source} />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
