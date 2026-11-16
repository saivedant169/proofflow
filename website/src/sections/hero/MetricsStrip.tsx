import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { animate, useInView, useReducedMotion } from 'motion/react'
import { Source } from '../../components/ui'
import { OF, STUDY_SOURCE, arm, derived, int, usd2 } from './data'
import Tip from './Tip'

const graph = arm('graph')
const full = arm('full')
const dense = arm('dense')
const bm25 = arm('bm25')
const hybrid = arm('hybrid')
const exact = arm('exact')

type Bar = { label: string; to: number; from?: number; lead?: boolean }

type Metric = {
  id: string
  to: number
  format: (n: number) => string
  suffix?: string
  label: string
  context: string
  bars: Bar[]
  receipt: string
}

/** Baseline comparison from the real-model study (./data.ts). No latency claim. */
const METRICS: Metric[] = [
  {
    id: 'correct',
    to: graph.correct,
    format: n => String(Math.round(n)),
    suffix: `/${OF}`,
    label: 'right, like full context',
    context: 'Affected reports refreshed',
    bars: [{ label: 'ProofFlow', to: 100, lead: true }, { label: 'Full context', to: 100 }],
    receipt: `ProofFlow and full context both refreshed ${OF}/${OF} affected reports across eight fresh cases, one sample each.`,
  },
  {
    id: 'tokens',
    to: derived.tokensSaved,
    format: n => int(n),
    label: 'fewer input tokens',
    context: `${derived.exposurePct}% of full context’s input`,
    bars: [{ label: 'Full context', to: 100 }, { label: 'ProofFlow', to: (graph.inputTokens / full.inputTokens) * 100, from: 100, lead: true }],
    receipt: `${int(graph.inputTokens)} vs ${int(full.inputTokens)} provider input tokens across all eight cases. Excluding the no-op case, ProofFlow used ${derived.exposurePct}% of full context’s input.`,
  },
  {
    id: 'cost',
    to: Math.round(derived.costLowerPct),
    format: n => String(Math.round(n)),
    suffix: '%',
    label: 'lower measured cost',
    context: `${usd2(graph.costUsd)} vs ${usd2(full.costUsd)} list price`,
    bars: [{ label: 'Full context', to: 100 }, { label: 'ProofFlow', to: (graph.costUsd / full.costUsd) * 100, from: 100, lead: true }],
    receipt: `Reported list cost for the whole study arm, not a subscription charge. It depends on cache treatment: the exact-flat ablation cost ${usd2(exact.costUsd)}.`,
  },
  {
    id: 'vector',
    to: derived.vsVector,
    format: n => n.toFixed(1),
    suffix: '×',
    label: 'more right than vector RAG',
    context: `${graph.correct} vs ${dense.correct}, same cost`,
    bars: [{ label: 'ProofFlow', to: 100, lead: true }, { label: 'Vector RAG', to: (dense.correct / OF) * 100 }],
    receipt: `Same evidence allowance and ${usd2(dense.costUsd)} list cost: vector RAG (BGE) ${dense.correct}/${OF}, BM25 ${bm25.correct}/${OF}, iterative hybrid ${hybrid.correct}/${OF}.`,
  },
]

function Count({ m, run, reduce }: { m: Metric; run: boolean; reduce: boolean }) {
  const [n, setN] = useState(reduce ? m.to : 0)
  useEffect(() => {
    if (!run) return
    if (reduce) { setN(m.to); return }
    const c = animate(0, m.to, { duration: 1.6, ease: [0.22, 1, 0.36, 1], onUpdate: setN })
    return () => c.stop()
  }, [run, reduce, m.to])
  return <>{m.format(n)}</>
}

export default function MetricsStrip() {
  const reduce = useReducedMotion() ?? false
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.3 })
  const run = inView || reduce

  return (
    <div className="hero-metrics" ref={ref} data-run={run ? 'true' : undefined}>
      <div className="wrap">
        <h2 className="sr-only">ProofFlow against today’s baselines</h2>
        <ul className="metrics">
          {METRICS.map((m, i) => (
            <li key={m.id} className={`metric metric-${m.id}`} style={{ '--delay': `${i * 140}ms` } as CSSProperties}>
              <Tip className="metric-tip" trigger={
                <>
                  <span className="metric-num figure">
                    <Count m={m} run={run} reduce={reduce} />
                    {m.suffix && <span className={`metric-suffix${m.suffix === '×' ? ' times' : ''}`}>{m.suffix}</span>}
                  </span>
                  <span className="sr-only">{m.label}. Show the source.</span>
                </>
              }>
                <span className="tip-text">{m.receipt}</span>
                <Source path={STUDY_SOURCE} />
              </Tip>
              <span className="metric-label" aria-hidden>{m.label}</span>
              <span className="metric-bars" aria-hidden>
                {m.bars.map(b => (
                  <span key={b.label} className={`metric-bar${b.lead ? ' is-lead' : ''}`}
                    style={{ '--to': `${b.to}%`, '--from': `${b.from ?? 0}%` } as CSSProperties}>
                    <span className="metric-bar-label">{b.label}</span>
                    <span className="metric-bar-track"><span className="metric-bar-fill" /></span>
                  </span>
                ))}
              </span>
              <span className="metric-context">{m.context}</span>
            </li>
          ))}
        </ul>
        <p className="metrics-foot">
          <span>One study, one sample per case. List prices; cost depends on caching. Exact-flat ablation ties on correctness. No latency claim.</span>
          <Source path={STUDY_SOURCE} />
        </p>
      </div>
    </div>
  )
}
