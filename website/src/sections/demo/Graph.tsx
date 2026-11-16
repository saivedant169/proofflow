import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { motion, useInView, useReducedMotion } from 'motion/react'
import {
  GRAPH_H, GRAPH_W, SLOTS, SLOT_DEF, STATE_TEXT, TOOL_LABEL, downstream,
  type NodeView, type ReportView, type Slot,
} from './model'

/** A state change travelling through the graph in dependency order, one depth level per step. */
export interface Wave {
  id: number
  origin: Slot | null
  prev: Record<Slot, NodeView>
  prevReports: ReportView[]
  depth: Partial<Record<Slot, number>>
  changed: Set<Slot>
  step: number
  max: number
  /** Milliseconds per dependency level. */
  stepMs: number
}

type Tone = 'idle' | 'stale' | 'blocked' | 'fresh'

const EDGES = SLOTS.flatMap(def => def.parents.map(parent => ({ from: parent, to: def.slot })))

/** An edge carries the signal only where it actually travelled: from a changed or stale parent. */
function edgeTone(parent: NodeView, child: NodeView): Tone {
  if (child.state === 'blocked' && (parent.state === 'removed' || parent.state === 'blocked')) return 'blocked'
  if ((child.state === 'stale' || child.state === 'unknown') && (parent.state === 'changed' || parent.state === 'stale' || parent.state === 'unknown')) return 'stale'
  if (child.badge === 'refreshed' && parent.state !== 'removed') return 'fresh'
  return 'idle'
}

function inkTone(node: NodeView): Tone {
  if (node.state === 'blocked' || node.state === 'removed') return 'blocked'
  if (node.state === 'stale' || node.state === 'unknown' || node.state === 'changed') return 'stale'
  return 'fresh'
}

/** Horizontal S-curve between node centres; nodes are opaque and drawn above, so threads meet their borders. */
function controls(from: Slot, to: Slot) {
  const a = SLOT_DEF[from]
  const b = SLOT_DEF[to]
  const mx = (a.cx + b.cx) / 2
  return [[a.cx, a.cy], [mx, a.cy], [mx, b.cy], [b.cx, b.cy]] as const
}

function edgePath(from: Slot, to: Slot) {
  const [p0, p1, p2, p3] = controls(from, to)
  return `M ${p0[0]} ${p0[1]} C ${p1[0]} ${p1[1]}, ${p2[0]} ${p2[1]}, ${p3[0]} ${p3[1]}`
}

/** Points along the curve, used as keyframes for the travelling pulse. */
function samples(from: Slot, to: Slot, count = 18) {
  const [p0, p1, p2, p3] = controls(from, to)
  const xs: number[] = []
  const ys: number[] = []
  for (let i = 0; i <= count; i++) {
    const t = i / count
    const u = 1 - t
    const w = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t]
    xs.push(w[0] * p0[0] + w[1] * p1[0] + w[2] * p2[0] + w[3] * p3[0])
    ys.push(w[0] * p0[1] + w[1] * p1[1] + w[2] * p2[1] + w[3] * p3[1])
  }
  return { xs, ys }
}

const reads = (slot: Slot) => SLOT_DEF[slot].parents.map(parent => SLOT_DEF[parent].label)

function valueLine(node: NodeView) {
  const def = SLOT_DEF[node.slot]
  if (node.state === 'changed') return `Now v${node.version}`
  if (node.state === 'stale' || node.state === 'unknown') return 'Withheld'
  if (node.state === 'blocked') return 'Blocked'
  if (node.state === 'removed') return 'Removed'
  if (def.layer === 'report') return node.badge === 'refreshed' ? 'Refreshed' : 'Current'
  return node.detail || 'Current'
}

function ariaLabel(node: NodeView) {
  const def = SLOT_DEF[node.slot]
  const state = node.badge === 'refreshed' ? 'Refreshed' : node.badge === 'reused' ? 'Current, reused' : node.state === 'changed' ? `Changed to version ${node.version}` : STATE_TEXT[node.state]
  const detail = node.state === 'current' && node.detail ? `, ${node.detail}` : ''
  const made = def.tool ? ` Made by ${TOOL_LABEL[def.tool]} from ${reads(node.slot).join(' and ')}.` : ' Source data.'
  return `${def.label}. ${state}${detail}.${made} Open details.`
}

function Node({ node, layout, selected, origin, preview, onSelect }: {
  node: NodeView; layout: 'canvas' | 'row'; selected: boolean; origin: boolean
  preview: 'in' | 'out' | null; onSelect: (slot: Slot) => void
}) {
  const def = SLOT_DEF[node.slot]
  const key = `${node.state}|${node.badge}|${node.recordId}`
  const last = useRef(key)
  const [ping, setPing] = useState(0)
  useEffect(() => {
    if (last.current === key) return
    last.current = key
    setPing(count => count + 1)
  }, [key])

  const style = layout === 'canvas'
    ? { left: `${(def.cx / GRAPH_W) * 100}%`, top: `${(def.cy / GRAPH_H) * 100}%`, '--col': Math.round(def.cx / 205) } as CSSProperties
    : undefined
  const classes = [
    'demo-node', `demo-node--${def.layer}`, `is-${node.state}`,
    node.badge ? `has-${node.badge}` : '', selected ? 'is-selected' : '', origin ? 'is-origin' : '',
    preview === 'in' ? 'is-preview' : preview === 'out' ? 'is-dim' : '',
  ].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} style={style} aria-pressed={selected}
      aria-label={ariaLabel(node)} onClick={() => onSelect(node.slot)}>
      {ping > 0 && <span key={ping} className="demo-node-ping" aria-hidden />}
      <span className="demo-node-mark" aria-hidden />
      <span className="demo-node-text">
        <span className="demo-node-name">{def.short}</span>
        <span className="demo-node-value figure">{valueLine(node)}</span>
      </span>
      {node.badge && <span className="demo-node-tag" aria-hidden>{node.badge === 'refreshed' ? 'Re-ran' : 'Reused'}</span>}
    </button>
  )
}

export default function Graph({ display, next, selected, onSelect, wave, preview }: {
  display: (slot: Slot) => NodeView
  /** End state of the current action; ink is drawn in the state a node is about to take. */
  next: Record<Slot, NodeView>
  selected: Slot | null
  onSelect: (slot: Slot) => void
  wave: Wave | null
  /** A source the visitor is about to correct: its downstream path is highlighted. */
  preview: Slot | null
}) {
  const reduce = useReducedMotion()
  const clip = useId().replace(/:/g, '')
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.35 })
  const revealed = reduce || inView
  const reach = preview ? downstream(preview) : null
  const previewOf = (slot: Slot) => (reach ? (reach.has(slot) ? 'in' : 'out') : null)

  // Ink only the threads the signal travels: into nodes that change state or re-run (not reuse-only).
  const inked = wave ? EDGES.filter(({ from, to }) => wave.changed.has(to)
    && next[to].badge !== 'reused'
    && (wave.depth[to] ?? 0) - 1 <= wave.step
    && (wave.depth[from] === 0 || wave.changed.has(from))) : []
  const travelling = wave ? inked.filter(({ to }) => (wave.depth[to] ?? 0) - 1 === wave.step) : []
  const seconds = (wave?.stepMs ?? 360) / 1000

  return (
    <div className="demo-graph" ref={ref}>
      <div className={`demo-canvas${revealed ? ' is-revealed' : ''}${reach ? ' has-preview' : ''}`} role="group"
        aria-label="Lineage graph. Four sources on the left feed tool runs, which feed two saved reports on the right.">
        <svg className="demo-svg" viewBox={`0 0 ${GRAPH_W} ${GRAPH_H}`} aria-hidden focusable="false">
          <defs>
            <clipPath id={clip}>
              <motion.rect x={-40} y={-40} height={GRAPH_H + 80}
                initial={{ width: reduce ? GRAPH_W + 80 : 0 }}
                animate={{ width: revealed ? GRAPH_W + 80 : 0 }}
                transition={{ duration: 1.8, ease: [0.65, 0, 0.35, 1] }} />
            </clipPath>
          </defs>
          <g clipPath={`url(#${clip})`}>
            {EDGES.map(({ from, to }) => {
              const tone = edgeTone(display(from), display(to))
              const lit = reach && reach.has(from) && reach.has(to)
              return (
                <path key={`${from}>${to}`} d={edgePath(from, to)}
                  className={`demo-edge is-${tone}${lit ? ' is-preview' : ''}${reach && !lit ? ' is-dim' : ''}`} />
              )
            })}
          </g>
          {wave && inked.map(({ from, to }) => (
            <motion.path key={`${wave.id}:${from}>${to}`} d={edgePath(from, to)}
              className={`demo-ink is-${inkTone(next[to])}`}
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
              transition={{ duration: seconds, ease: [0.65, 0, 0.35, 1] }} />
          ))}
          {wave && travelling.map(({ from, to }) => {
            const { xs, ys } = samples(from, to)
            return (
              <motion.g key={`pulse:${wave.id}:${from}>${to}`} className={`demo-pulse is-${inkTone(next[to])}`}
                initial={{ opacity: 0 }} animate={{ opacity: [0, 1, 1, 0] }}
                transition={{ duration: seconds, times: [0, 0.12, 0.8, 1] }}>
                <motion.circle r={14} className="demo-pulse-halo" initial={{ cx: xs[0], cy: ys[0] }}
                  animate={{ cx: xs, cy: ys }} transition={{ duration: seconds, ease: [0.65, 0, 0.35, 1] }} />
                <motion.circle r={5} className="demo-pulse-core" initial={{ cx: xs[0], cy: ys[0] }}
                  animate={{ cx: xs, cy: ys }} transition={{ duration: seconds, ease: [0.65, 0, 0.35, 1] }} />
              </motion.g>
            )
          })}
        </svg>
        {SLOTS.map(def => (
          <Node key={def.slot} node={display(def.slot)} layout="canvas" selected={selected === def.slot}
            origin={wave?.origin === def.slot} preview={previewOf(def.slot)} onSelect={onSelect} />
        ))}
      </div>

      <ol className={`demo-list${reach ? ' has-preview' : ''}`} aria-label="Lineage, sources first, in dependency order">
        {SLOTS.map(def => {
          const node = display(def.slot)
          return (
            <li key={def.slot} className={`demo-list-item demo-list-item--${def.layer} is-${node.state}${node.badge ? ` has-${node.badge}` : ''}`}>
              <Node node={node} layout="row" selected={selected === def.slot}
                origin={wave?.origin === def.slot} preview={previewOf(def.slot)} onSelect={onSelect} />
            </li>
          )
        })}
      </ol>

      <ul className="demo-legend" aria-label="Legend">
        <li><span className="demo-legend-mark is-current" aria-hidden />Current</li>
        <li><span className="demo-legend-mark is-stale" aria-hidden />Withheld</li>
        <li><span className="demo-legend-mark is-fresh" aria-hidden />Re-ran</li>
        <li><span className="demo-legend-mark is-blocked" aria-hidden />Blocked</li>
      </ul>
    </div>
  )
}
