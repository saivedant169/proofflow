import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { motion, useInView, useReducedMotion } from 'motion/react'
import { ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import { Button, StateTag } from '../../components/ui'
import { EDGES, NARROW, NODES, STEPS, WIDE, describe, type ChainNode, type NodeId, type NodeState, type NodeView } from './chain'
import { edgeGeometry, type Box } from './geometry'
import { useNarrow } from './useNarrow'

/** How far each node sits from the changed source; the stale pulse and refresh re-ink travel in this order. */
const DEPTH: Record<NodeId, number> = { fx: 0, tool: 0, net: 1, exec: 1, regional: 2, support: 3, company: 3, eu: 3 }
const BEAT = 0.38 // seconds per hop
const IDS = NODES.map(n => n.id)
const fill = (step: number) => Object.fromEntries(IDS.map(id => [id, step])) as Record<NodeId, number>

function viewFor(id: NodeId, step: number): NodeView {
  return STEPS[step].view[id] ?? { state: 'current' }
}

/**
 * Each node adopts a new step's state when the travelling signal reaches it. `animate` is read
 * only on the render where the step changed, so later re-renders do not cut the stagger short.
 */
function useShownSteps(step: number, animate: boolean) {
  const [shown, setShown] = useState(() => fill(step))
  const animateRef = useRef(animate)
  animateRef.current = animate
  useEffect(() => {
    const animate = animateRef.current
    if (!animate) {
      setShown(fill(step))
      return
    }
    const timers = IDS.map(id => window.setTimeout(() => setShown(s => ({ ...s, [id]: step })), DEPTH[id] * BEAT * 1000))
    return () => timers.forEach(t => window.clearTimeout(t))
  }, [step])
  return shown
}

export function ChainFigure() {
  const [step, setStep] = useState(0)
  const previous = useRef(0)
  const forward = step > previous.current
  useEffect(() => { previous.current = step }, [step])

  const reduce = useReducedMotion() ?? false
  const narrow = useNarrow()
  const layout = narrow ? NARROW : WIDE
  const current = STEPS[step]
  const stateChange = forward && !reduce && (current.key === 'change' || current.key === 'refresh')
  const build = forward && !reduce
  const shown = useShownSteps(step, stateChange)

  const uid = useId().replace(/:/g, '')
  const hatchId = `how-hatch-${uid}`
  const titleId = `how-chain-title-${uid}`
  const prevVisible = new Set(STEPS[Math.max(0, previous.current)].visible)
  const visible = new Set(current.visible)

  // Build the chain once when it first comes into view (steps 1-4), so a skimming reader
  // never meets an empty diagram. Any user interaction stops the auto-build.
  const figureRef = useRef<HTMLElement>(null)
  const touched = useRef(false)
  const inView = useInView(figureRef, { once: true, amount: 0.2 })
  useEffect(() => {
    if (!inView || touched.current) return
    if (reduce) { setStep(3); return }
    const timers = [1, 2, 3].map((s, i) => window.setTimeout(() => {
      if (!touched.current) setStep(s)
    }, 900 + i * 1500))
    return () => timers.forEach(t => window.clearTimeout(t))
  }, [inView, reduce])

  const go = (next: number) => {
    touched.current = true
    setStep(Math.max(0, Math.min(STEPS.length - 1, next)))
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); go(step + 1) }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); go(step - 1) }
  }

  const last = step === STEPS.length - 1

  return (
    <figure className="how-figure panel" ref={figureRef}>
      <ol className="how-steps" aria-label="Steps of the lineage chain" onKeyDown={onKey}
        style={{ ['--how-progress' as string]: String(step / (STEPS.length - 1)) }}>
        {STEPS.map((s, i) => (
          <li key={s.key}>
            <button type="button" className="how-step" aria-current={i === step ? 'step' : undefined}
              data-done={i < step || undefined} onClick={() => go(i)}>
              <span className="how-step-n figure" aria-hidden>{i + 1}</span>
              <span className="how-step-label">{s.label}</span>
            </button>
          </li>
        ))}
      </ol>

      <div className="how-canvas">
        <svg className={`how-chain ${narrow ? 'how-chain--narrow' : ''}`} viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="img" aria-labelledby={titleId} preserveAspectRatio="xMidYMid meet">
          <title id={titleId}>{describe(current)}</title>
          <defs>
            <pattern id={hatchId} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect className="how-hatch-bg" width="8" height="8" />
              <rect className="how-hatch-line" width="3.2" height="8" />
            </pattern>
          </defs>

          {/* Edges: a faint base, then a colored thread drawn over it */}
          {EDGES.map(edge => {
            const a = layout.nodes[edge.from]
            const b = layout.nodes[edge.to]
            const g = edgeGeometry(a, b, layout.axis)
            const isVisible = visible.has(edge.from) && visible.has(edge.to)
            if (!isVisible) return <path key={edge.id} d={g.d} className="how-edge-ghost" />
            const isNew = !(prevVisible.has(edge.from) && prevVisible.has(edge.to))
            // Orange only along the path from the changed source; mint where refresh wrote new edges.
            const targetState = viewFor(edge.to, step).state
            const sourceState = viewFor(edge.from, step).state
            const tone = targetState === 'stale' && sourceState === 'stale' ? 'stale'
              : targetState === 'refreshed' ? 'fresh' : 'thread'
            const delay = stateChange ? edge.depth * BEAT : isNew && build ? 0.12 : 0
            const animateDraw = (stateChange && tone !== 'thread') || (isNew && build)
            const showLabel = edge.label && g.span > 44 && step <= 3
            return (
              <g key={edge.id}>
                <path d={g.d} className="how-edge-base" />
                <motion.path key={`${edge.id}-${tone}`} d={g.d} className={`how-edge how-edge--${tone}`}
                  initial={animateDraw ? { pathLength: 0 } : false} animate={{ pathLength: 1 }}
                  transition={{ duration: stateChange ? BEAT : 0.45, delay, ease: 'easeInOut' }} />
                {showLabel && (
                  <motion.text className="how-edge-label" x={g.horizontal ? g.mid.x : g.mid.x + 7} y={g.horizontal ? g.mid.y - 8 : g.mid.y + 4}
                    textAnchor={g.horizontal ? 'middle' : 'start'}
                    initial={isNew && build ? { opacity: 0 } : false} animate={{ opacity: 1 }} transition={{ delay: 0.45, duration: 0.2 }}>
                    {edge.label}
                  </motion.text>
                )}
              </g>
            )
          })}

          {NODES.map(node => {
            const box = layout.nodes[node.id]
            if (!visible.has(node.id)) return <GhostNode key={node.id} node={node} box={box} />
            const isNew = !prevVisible.has(node.id)
            // A node that is fed by a thread appears once that thread has been drawn into it.
            const fed = EDGES.some(e => e.to === node.id && visible.has(e.from))
            const appearDelay = isNew && build && fed ? 0.5 : 0
            return (
              <ChainNodeView key={node.id} node={node} box={box} view={viewFor(node.id, shown[node.id])}
                hatchId={hatchId} appear={isNew && build} appearDelay={appearDelay} />
            )
          })}
        </svg>
      </div>

      <figcaption className="how-caption">
        <div className="how-caption-text" aria-live="polite">
          <p className="how-caption-title">
            <span className="sr-only">Step {step + 1} of {STEPS.length}: </span>{current.title}
          </p>
          <p className="how-caption-body">{current.body}</p>
          {current.points && (
            <ul className="how-points">
              {current.points.map(p => <li key={p}>{p}</li>)}
            </ul>
          )}
          {current.key === 'change' && (
            <p className="how-caption-tags"><StateTag state="withheld">Revenue withheld</StateTag><StateTag state="current">Support current</StateTag></p>
          )}
          {current.key === 'refresh' && (
            <p className="how-caption-tags"><StateTag state="refreshed">Revenue refreshed</StateTag><StateTag state="reused">Support reused</StateTag></p>
          )}
        </div>
        <div className="how-controls">
          <Button variant="secondary" onClick={() => go(step - 1)} disabled={step === 0}
            icon={<ChevronLeft aria-hidden size={18} />}>Back</Button>
          {last
            ? <Button variant="primary" onClick={() => go(0)} icon={<RotateCcw aria-hidden size={17} />}>Start over</Button>
            : <Button variant="primary" onClick={() => go(step + 1)} icon={<ChevronRight aria-hidden size={18} />}>
                {step === 3 ? 'Change the rate' : step === 4 ? 'Refresh' : 'Next step'}
              </Button>}
        </div>
      </figcaption>
    </figure>
  )
}

function radiusFor(node: ChainNode, box: Box) {
  return node.kind === 'execution' || node.kind === 'tool' ? box.h / 2 : 6
}

function GhostNode({ node, box }: { node: ChainNode; box: Box }) {
  return (
    <rect className="how-node-ghost" x={box.x - box.w / 2} y={box.y - box.h / 2} width={box.w} height={box.h}
      rx={radiusFor(node, box)} aria-hidden />
  )
}

function ChainNodeView({ node, box, view, hatchId, appear, appearDelay }:
  { node: ChainNode; box: Box; view: NodeView; hatchId: string; appear: boolean; appearDelay: number }) {
  const rx = radiusFor(node, box)
  const state: NodeState = view.state
  const sub = view.sub ?? node.sub
  const pad = node.kind === 'execution' || node.kind === 'tool' ? 18 : node.kind === 'source' ? 16 : 12
  const withheld = node.kind === 'report' && state === 'stale'
  return (
    <motion.g className={`how-node how-node--${node.kind} is-${state}`}
      transform={`translate(${box.x - box.w / 2} ${box.y - box.h / 2})`}
      initial={appear ? { opacity: 0 } : false} animate={{ opacity: 1 }}
      transition={{ duration: 0.25, delay: appearDelay }}>
      {node.kind === 'report' && <rect className="how-node-outer" x={-4} y={-4} width={box.w + 8} height={box.h + 8} rx={rx + 3} />}
      <rect className="how-node-box" width={box.w} height={box.h} rx={rx} />
      <rect className="how-node-hatch" width={box.w} height={box.h} rx={rx} fill={`url(#${hatchId})`}
        style={{ opacity: state === 'stale' ? 1 : 0 }} />
      <rect className="how-node-fresh" width={box.w} height={box.h} rx={rx} style={{ opacity: state === 'refreshed' ? 1 : 0 }} />
      <rect className="how-node-stroke" width={box.w} height={box.h} rx={rx} />
      {node.kind === 'source' && <rect className="how-node-bar" x={0} y={0} width={5} height={box.h} rx={2} />}

      <text className={node.kind === 'tool' ? 'how-node-code' : 'how-node-title'} x={pad} y={node.kind === 'tool' ? box.h / 2 - 3 : 25}>
        {node.title}
      </text>
      {node.kind === 'report' ? (
        <>
          <text className="how-node-sub" x={pad} y={46}>{node.claim}</text>
          <text className={`how-node-value figure ${withheld ? 'is-withheld' : ''}`} x={pad} y={76}>
            {withheld ? 'Withheld' : view.value}
          </text>
        </>
      ) : (
        <text className="how-node-sub" x={pad} y={node.kind === 'tool' ? box.h / 2 + 13 : 45}>{sub}</text>
      )}
    </motion.g>
  )
}
