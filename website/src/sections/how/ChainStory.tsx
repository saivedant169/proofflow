import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useScroll } from 'motion/react'
import {
  APPEAR, CHANGE_AT, EDGES, NARROW, NODES, PHASES, PHASE_LEN, REFRESH_AT, VALUES, WIDE,
  clamp01, describe, span, stateAt, subAt, type ChainEdge, type ChainNode, type Layout,
} from './chain'
import { edgeGeometry, type Box } from './geometry'
import { StateTokens, type TokenState } from './StateTokens'
import { useNarrow } from './useNarrow'

/** Where each chapter is fully built; the rail jumps here. */
const phaseEnd = (i: number) => Math.min(0.995, (i + 0.9) * PHASE_LEN)
/** Reduced motion: a static, fully built chain (end of "Report claim"). */
const STATIC_BUILT = phaseEnd(3)
const QUANT = 800

export function ChainStory() {
  const trackRef = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion() ?? false
  const narrow = useNarrow()
  const layout = narrow ? NARROW : WIDE

  const { scrollYProgress } = useScroll({ target: trackRef, offset: ['start start', 'end end'] })
  const [scrollP, setScrollP] = useState(0)
  const [staticP, setStaticP] = useState(STATIC_BUILT)
  useMotionValueEvent(scrollYProgress, 'change', v => setScrollP(Math.round(v * QUANT) / QUANT))
  useEffect(() => { setScrollP(Math.round(scrollYProgress.get() * QUANT) / QUANT) }, [scrollYProgress])

  const p = reduce ? staticP : scrollP
  const phase = Math.min(PHASES.length - 1, Math.floor(p / PHASE_LEN))
  const current = PHASES[phase]

  const goTo = (i: number) => {
    const target = phaseEnd(i)
    if (reduce) { setStaticP(target); return }
    const track = trackRef.current
    if (!track) return
    const top = track.getBoundingClientRect().top + window.scrollY
    const total = track.offsetHeight - window.innerHeight
    window.scrollTo({ top: top + target * total, behavior: 'smooth' })
  }

  const live = new Set<TokenState>(['current'])
  if (NODES.some(n => p >= n.shown && stateAt(n, p) === 'stale')) live.add('stale')

  return (
    <div className="how-track" ref={trackRef} data-static={reduce || undefined}>
      <div className="how-sticky">
        <div className="how-stage wrap">
          <Rail p={p} phase={phase} onGo={goTo} />
          <div className="how-canvas">
            <Chain p={p} layout={layout} narrow={narrow} />
          </div>
          <div className="how-foot">
            <div className="how-caption" aria-live="polite">
              <span className="how-count figure" aria-hidden>
                {String(phase + 1).padStart(2, '0')}<span>/{String(PHASES.length).padStart(2, '0')}</span>
              </span>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={current.key} className="how-caption-text"
                  initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}>
                  <p className="how-caption-label"><span className="sr-only">Step {phase + 1} of {PHASES.length}: </span>{current.label}</p>
                  <p className="how-caption-body">{current.caption}</p>
                </motion.div>
              </AnimatePresence>
            </div>
            <StateTokens live={live} />
          </div>
        </div>
      </div>
    </div>
  )
}

function Rail({ p, phase, onGo }: { p: number; phase: number; onGo: (i: number) => void }) {
  return (
    <nav className="how-rail" aria-label="Chain chapters" style={{ ['--how-p' as string]: String(clamp01(p / PHASE_LEN / (PHASES.length - 1))) }}>
      <ol>
        {PHASES.map((ph, i) => (
          <li key={ph.key}>
            <button type="button" className={`how-rail-step how-rail-step--${ph.key}`} onClick={() => onGo(i)}
              aria-current={i === phase ? 'step' : undefined} data-done={i < phase || undefined}>
              <span className="how-rail-dot" aria-hidden />
              <span className="how-rail-label">{ph.label}</span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}

function Chain({ p, layout, narrow }: { p: number; layout: Layout; narrow: boolean }) {
  const uid = useId().replace(/:/g, '')
  const hatchId = `how-hatch-${uid}`
  const titleId = `how-chain-title-${uid}`
  const fx = layout.nodes.fx
  const changeRing = span(p, [CHANGE_AT - 0.004, CHANGE_AT + 0.03])
  const refreshRing = span(p, [REFRESH_AT - 0.004, REFRESH_AT + 0.03])
  return (
    <svg className={`how-chain ${narrow ? 'how-chain--narrow' : ''}`} viewBox={`0 0 ${layout.width} ${layout.height}`}
      role="img" aria-labelledby={titleId} preserveAspectRatio="xMidYMid meet">
      <title id={titleId}>{describe(p)}</title>
      <defs>
        <pattern id={hatchId} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect className="how-hatch-bg" width="8" height="8" />
          <rect className="how-hatch-line" width="3.2" height="8" />
        </pattern>
      </defs>

      {EDGES.map(e => <Edge key={e.id} edge={e} layout={layout} p={p} narrow={narrow} />)}

      {/* The correction lands on the source, then the refresh starts from it. */}
      <Ring box={fx} t={changeRing} tone="stale" />
      <Ring box={fx} t={refreshRing} tone="fresh" />

      {NODES.map(n => <Node key={n.id} node={n} box={layout.nodes[n.id]} p={p} hatchId={hatchId} />)}
    </svg>
  )
}

function Ring({ box, t, tone }: { box: Box; t: number; tone: 'stale' | 'fresh' }) {
  if (t <= 0 || t >= 1) return null
  const grow = 4 + t * 22
  return (
    <rect className={`how-ring how-ring--${tone}`} x={box.x - box.w / 2 - grow} y={box.y - box.h / 2 - grow}
      width={box.w + grow * 2} height={box.h + grow * 2} rx={8 + grow} style={{ opacity: 1 - t }} />
  )
}

function Edge({ edge, layout, p, narrow }: { edge: ChainEdge; layout: Layout; p: number; narrow: boolean }) {
  const g = edgeGeometry(layout.nodes[edge.from], layout.nodes[edge.to], layout.axis)
  const drawn = span(p, edge.draw)
  const pulse = edge.pulse ? span(p, edge.pulse) : 0
  const ink = span(p, edge.ink)
  // The orange pulse stays on its edges until the mint re-ink covers them.
  const pulseShown = pulse > 0 && ink < 1
  const pathRef = useRef<SVGPathElement>(null)
  const headRef = useRef<SVGCircleElement>(null)
  const travelling = pulse > 0 && pulse < 1 ? { t: pulse, tone: 'stale' } : ink > 0 && ink < 1 ? { t: ink, tone: 'fresh' } : null

  useLayoutEffect(() => {
    const path = pathRef.current
    const head = headRef.current
    if (!path || !head || !travelling) return
    const pt = path.getPointAtLength(travelling.t * path.getTotalLength())
    head.setAttribute('cx', String(pt.x))
    head.setAttribute('cy', String(pt.y))
  })

  const labelAlpha = edge.label && (!narrow || g.span > 44)
    ? span(p, [edge.draw[1], edge.draw[1] + 0.02]) * (1 - span(p, [CHANGE_AT - 0.03, CHANGE_AT - 0.005]))
    : 0
  const dash = (t: number) => ({ strokeDasharray: '1 1', strokeDashoffset: 1 - t })

  return (
    <g>
      <path ref={pathRef} d={g.d} className="how-edge-ghost" />
      {drawn > 0 && <path d={g.d} pathLength={1} className="how-edge how-edge--thread" style={dash(drawn)} />}
      {pulseShown && <path d={g.d} pathLength={1} className="how-edge how-edge--stale" style={dash(pulse)} />}
      {ink > 0 && <path d={g.d} pathLength={1} className="how-edge how-edge--fresh" style={dash(ink)} />}
      {travelling && <circle ref={headRef} r={5} className={`how-dot how-dot--${travelling.tone}`} />}
      {labelAlpha > 0 && (
        <text className="how-edge-label" style={{ opacity: labelAlpha }}
          x={g.horizontal ? g.mid.x : g.mid.x + 7} y={g.horizontal ? g.mid.y - 8 : g.mid.y + 4}
          textAnchor={g.horizontal ? 'middle' : 'start'}>
          {edge.label}
        </text>
      )}
    </g>
  )
}

const radiusFor = (node: ChainNode, box: Box) => (node.kind === 'execution' || node.kind === 'tool' ? box.h / 2 : 8)

function Node({ node, box, p, hatchId }: { node: ChainNode; box: Box; p: number; hatchId: string }) {
  const a = node.shown === 0 ? 1 : clamp01((p - (node.shown - APPEAR)) / APPEAR)
  const rx = radiusFor(node, box)
  const x0 = box.x - box.w / 2
  const y0 = box.y - box.h / 2
  if (a <= 0) {
    return <rect className="how-node-ghost" x={x0} y={y0} width={box.w} height={box.h} rx={rx} aria-hidden />
  }
  const state = stateAt(node, p)
  const sub = subAt(node, p)
  const pad = node.kind === 'execution' || node.kind === 'tool' ? 18 : node.kind === 'source' ? 17 : 13
  const report = node.kind === 'report'
  const withheld = report && state === 'stale'
  const value = report ? (state === 'refreshed' ? VALUES[node.id as 'company' | 'eu'].after : VALUES[node.id as 'company' | 'eu'].before) : ''
  return (
    <g className={`how-node how-node--${node.kind} is-${state}`}
      transform={`translate(${x0} ${y0 + (1 - a) * 10})`} style={{ opacity: a }}>
      {report && <rect className="how-node-outer" x={-4} y={-4} width={box.w + 8} height={box.h + 8} rx={rx + 3} />}
      <rect className="how-node-box" width={box.w} height={box.h} rx={rx} />
      <rect className="how-node-hatch" width={box.w} height={box.h} rx={rx} fill={`url(#${hatchId})`}
        style={{ opacity: state === 'stale' ? 1 : 0 }} />
      <rect className="how-node-fresh" width={box.w} height={box.h} rx={rx} style={{ opacity: state === 'refreshed' ? 1 : 0 }} />
      <rect className="how-node-stroke" width={box.w} height={box.h} rx={rx} />
      {node.kind === 'source' && <rect className="how-node-bar" x={0} y={8} width={4} height={box.h - 16} rx={2} />}

      <text className={node.kind === 'tool' ? 'how-node-code' : 'how-node-title'} x={pad} y={node.kind === 'tool' ? box.h / 2 - 3 : 25}>
        {node.title}
      </text>
      {report ? (
        <>
          <text className="how-node-sub" x={pad} y={46}>{node.claim}</text>
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.text key={withheld ? 'w' : value} className={`how-node-value figure ${withheld ? 'is-withheld' : ''}`}
              x={pad} y={77} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}>
              {withheld ? 'Withheld' : value}
            </motion.text>
          </AnimatePresence>
        </>
      ) : (
        <text className="how-node-sub" x={pad} y={node.kind === 'tool' ? box.h / 2 + 13 : 45}>{sub}</text>
      )}
    </g>
  )
}
