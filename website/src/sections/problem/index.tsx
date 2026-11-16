import { useRef, useState, type CSSProperties } from 'react'
import { useInView, useReducedMotion } from 'motion/react'
import { FileStack, ScanSearch, TextSearch, Waypoints, type LucideIcon } from 'lucide-react'
import { Source, StateTag, type ClaimState } from '../../components/ui'
import { headline } from '../../content/facts'
import { OF, STUDY_SOURCE, arm, derived, int, usd2, type ArmId } from '../hero/data'
import Tip from '../hero/Tip'
import './styles.css'

/*
 * Each 10×10 grid illustrates one approach's context: every tile is 1% of full context. Tiles on the dependency
 * path ("needed") are what a refresh actually depends on (35 tiles, close to ProofFlow's 35.17% of full
 * context's input across all cases). The capped arms read the same 35-tile budget. Counts of hits are scaled
 * from each arm's measured correct/32. Illustration only; the numbers beside each grid are measured.
 */

type Cell = 'hit' | 'waste' | 'miss' | 'idle'

const N = 10
const idx = (r: number, c: number) => r * N + c
const run = (cells: [number, number][]) => cells.map(([r, c]) => idx(r, c))
const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => a + i)

/** The dependency path: a trunk with branches. 35 tiles. */
const PATH = new Set<number>([
  ...run(range(0, 9).map(r => [r, 4] as [number, number])),
  ...run(range(1, 3).map(c => [3, c] as [number, number])),
  ...run(range(4, 8).map(r => [r, 1] as [number, number])),
  ...run(range(5, 8).map(c => [6, c] as [number, number])),
  ...run(range(0, 5).map(r => [r, 8] as [number, number])),
  ...run(range(5, 7).map(c => [1, c] as [number, number])),
  ...run([[8, 2], [8, 3], [0, 0], [0, 1]]),
])

const hash = (i: number, salt: number) => (Math.imul(i + 1, 2654435761) ^ Math.imul(salt + 7, 40503)) >>> 0

/** Deterministically pick `hits` path tiles and fill the rest of a 35-tile budget off the path. */
function grid(hits: number, salt: number, readAll = false): Cell[] {
  const all = range(0, N * N - 1)
  if (readAll) return all.map(i => (PATH.has(i) ? 'hit' : 'waste'))
  const onPath = all.filter(i => PATH.has(i)).sort((a, b) => hash(a, salt) - hash(b, salt))
  const offPath = all.filter(i => !PATH.has(i)).sort((a, b) => hash(a, salt + 3) - hash(b, salt + 3))
  const read = new Set([...onPath.slice(0, hits), ...offPath.slice(0, PATH.size - hits)])
  return all.map(i => (PATH.has(i) ? (read.has(i) ? 'hit' : 'miss') : read.has(i) ? 'waste' : 'idle'))
}

const scaled = (correct: number) => Math.round((correct / OF) * PATH.size)

type Lane = {
  id: ArmId
  name: string
  icon: LucideIcon
  value: string
  unit: string
  chip: string
  state: ClaimState
  cells: Cell[]
  receipt: string
}

const full = arm('full')
const dense = arm('dense')
const bm25 = arm('bm25')
const graph = arm('graph')
const exact = arm('exact')
const retail = headline.retail
const retailOf = (m: string) => retail.comparators.find(c => c.method === m)?.refreshed

const LANES: Lane[] = [
  {
    id: 'full',
    name: 'Re-read everything',
    icon: FileStack,
    value: int(full.inputTokens),
    unit: 'input tokens',
    chip: `${(full.inputTokens / graph.inputTokens).toFixed(1)}× ProofFlow’s input`,
    state: 'unknown',
    cells: grid(PATH.size, 0, true),
    receipt: `Full context refreshed ${full.correct}/${OF}, but read ${int(full.inputTokens)} input tokens at ${usd2(full.costUsd)} measured list cost. ProofFlow: ${int(graph.inputTokens)} and ${usd2(graph.costUsd)}.`,
  },
  {
    id: 'dense',
    name: 'Vector RAG',
    icon: ScanSearch,
    value: `${dense.correct}/${OF}`,
    unit: 'affected reports right',
    chip: `Misses ${OF - dense.correct} of ${OF}`,
    state: 'stale',
    cells: grid(scaled(dense.correct), 11),
    receipt: `BGE dense retrieval at the same evidence allowance (${int(dense.inputTokens)} input tokens, ${usd2(dense.costUsd)}). Retail benchmark: ${retailOf('Dense BGE')}/${retail.of}.`,
  },
  {
    id: 'bm25',
    name: 'Keyword search',
    icon: TextSearch,
    value: `${bm25.correct}/${OF}`,
    unit: 'affected reports right',
    chip: `Misses ${OF - bm25.correct} of ${OF}`,
    state: 'stale',
    cells: grid(scaled(bm25.correct), 5),
    receipt: `BM25 at the same evidence allowance (${int(bm25.inputTokens)} input tokens, ${usd2(bm25.costUsd)}). Retail benchmark: ${retailOf('BM25')}/${retail.of}.`,
  },
  {
    id: 'graph',
    name: 'Follow the lineage',
    icon: Waypoints,
    value: `${graph.correct}/${OF}`,
    unit: 'affected reports right',
    chip: `At ${derived.exposurePct}% of input`,
    state: 'current',
    cells: grid(PATH.size, 0),
    receipt: `ProofFlow: ${int(graph.inputTokens)} input tokens, ${usd2(graph.costUsd)} list cost; ${derived.exposurePct}% of full context’s input excluding the no-op case. The exact-flat ablation ties at ${exact.correct}/${OF}.`,
  },
]

function Waffle({ cells, lane }: { cells: Cell[]; lane: number }) {
  return (
    <svg className="waffle" viewBox="0 0 100 100" aria-hidden focusable="false">
      {cells.map((type, i) => (
        <rect key={i} x={(i % N) * 10 + 1} y={Math.floor(i / N) * 10 + 1} width={8} height={8} rx={1.6}
          className={`cell is-${type}${PATH.has(i) ? ' on-path' : ''}`}
          style={{ '--k': (i % N) + Math.floor(i / N) + lane * 3 } as CSSProperties} />
      ))}
    </svg>
  )
}

export default function Problem() {
  const reduce = useReducedMotion() ?? false
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.25 })
  const [showPath, setShowPath] = useState(false)

  return (
    <section id="problem" className="section problem-section" aria-labelledby="problem-title">
      <div className="wrap">
        <header className="problem-head">
          <h2 id="problem-title" className="problem-title">Today’s fixes are heavy or blind.</h2>
          <p className="problem-lede">
            Re-reading everything burns tokens; similarity search stays cheap but misses what actually depends on the change.
          </p>
        </header>

        <div className="lanes-bar">
          <button type="button" role="switch" aria-checked={showPath} className="path-switch" onClick={() => setShowPath(v => !v)}>
            <span className="path-switch-track" aria-hidden><span /></span>
            Show the dependency path
          </button>
          <ul className="lanes-key" aria-hidden>
            <li><span className="key is-hit" />Needed, read</li>
            <li><span className="key is-waste" />Read, not needed</li>
            <li><span className="key is-miss" />Needed, missed</li>
          </ul>
        </div>

        <div ref={ref} className="lanes" data-run={inView || reduce ? 'true' : undefined} data-path={showPath ? 'true' : undefined}>
          {LANES.map((l, i) => {
            const Icon = l.icon
            return (
              <article key={l.id} className={`lane lane-${l.id}`} aria-labelledby={`lane-${l.id}`}>
                <h3 className="lane-name" id={`lane-${l.id}`}>
                  <Icon size={18} strokeWidth={2} aria-hidden />
                  {l.name}
                </h3>
                <Waffle cells={l.cells} lane={i} />
                <Tip className="lane-tip" trigger={
                  <>
                    <span className="lane-num figure">{l.value}</span>
                    <span className="sr-only"> {l.unit}. Show the source.</span>
                  </>
                }>
                  <span className="tip-text">{l.receipt}</span>
                  <Source path={STUDY_SOURCE} />
                </Tip>
                <span className="lane-unit" aria-hidden>{l.unit}</span>
                <StateTag state={l.state}>{l.chip}</StateTag>
              </article>
            )
          })}
        </div>

        <p className="problem-foot">
          <span>Tiles illustrate context, 1% each. Numbers: real-model study, eight cases, same evidence allowance.</span>
          <Source path={STUDY_SOURCE} />
        </p>
      </div>
    </section>
  )
}
