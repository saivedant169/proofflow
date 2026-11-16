import type { CSSProperties } from 'react'
import { motion } from 'motion/react'
import {
  GRAPH_H, GRAPH_W, SLOTS, SLOT_DEF, STATE_TEXT, TOOL_LABEL,
  type Layer, type NodeView, type ReportView, type Slot,
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

/** Centre-to-centre curve; nodes are opaque and drawn above, so threads meet their borders. */
function edgePath(from: Slot, to: Slot) {
  const a = SLOT_DEF[from]
  const b = SLOT_DEF[to]
  const dy = (b.cy - a.cy) / 2
  return `M ${a.cx} ${a.cy} C ${a.cx} ${a.cy + dy}, ${b.cx} ${b.cy - dy}, ${b.cx} ${b.cy}`
}

const reads = (slot: Slot) => SLOT_DEF[slot].parents.map(parent => SLOT_DEF[parent].label)

function stateLine(node: NodeView) {
  if (node.badge === 'refreshed') return 'Refreshed'
  if (node.badge === 'reused') return 'Reused'
  if (node.state === 'current') return node.detail || 'Current'
  if (node.state === 'changed') return `Changed to v${node.version}`
  return STATE_TEXT[node.state]
}

function ariaLabel(node: NodeView) {
  const def = SLOT_DEF[node.slot]
  const state = node.badge === 'refreshed' ? 'Refreshed' : node.badge === 'reused' ? 'Current, reused' : node.state === 'changed' ? `Changed to version ${node.version}` : STATE_TEXT[node.state]
  const detail = node.state === 'current' && node.detail ? `, ${node.detail}` : ''
  const made = def.tool ? ` Made by ${TOOL_LABEL[def.tool]} from ${reads(node.slot).join(' and ')}.` : ' Source data.'
  return `${def.label}. ${state}${detail}.${made}`
}

function NodeButton({ node, selected, origin, onSelect, layout }: {
  node: NodeView; selected: boolean; origin: boolean; onSelect: (slot: Slot) => void; layout: 'canvas' | 'row'
}) {
  const def = SLOT_DEF[node.slot]
  const style: CSSProperties | undefined = layout === 'canvas'
    ? { left: `${(def.cx / GRAPH_W) * 100}%`, top: `${(def.cy / GRAPH_H) * 100}%` }
    : undefined
  const classes = [
    'demo-node', `demo-node--${def.layer}`, `is-${node.state}`,
    node.badge ? `has-${node.badge}` : '', selected ? 'is-selected' : '', origin ? 'is-origin' : '',
  ].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} style={style} aria-pressed={selected}
      aria-label={ariaLabel(node)} onClick={() => onSelect(node.slot)}>
      <span className="demo-node-label">{def.label}</span>
      <span className="demo-node-state figure">
        <span className="demo-glyph" aria-hidden />
        <span className="demo-node-state-text">{stateLine(node)}</span>
      </span>
      {layout === 'row' && def.tool && (
        <span className="demo-node-reads">{TOOL_LABEL[def.tool]}, from {reads(node.slot).join(' and ')}</span>
      )}
    </button>
  )
}

const LAYERS: { layer: Layer; title: string }[] = [
  { layer: 'source', title: 'Sources' },
  { layer: 'metric', title: 'Tool results, in dependency order' },
  { layer: 'report', title: 'Saved reports' },
]

export default function Graph({ display, next, selected, onSelect, wave, origin }: {
  display: (slot: Slot) => NodeView
  /** End state of the current action; ink is drawn in the state a node is about to take. */
  next: Record<Slot, NodeView>
  selected: Slot | null
  onSelect: (slot: Slot) => void
  wave: Wave | null
  origin: Slot | null
}) {
  // Ink only the threads the signal travels: into nodes that change state or re-run (not reuse-only).
  const inked = wave ? EDGES.filter(({ from, to }) => wave.changed.has(to)
    && next[to].badge !== 'reused'
    && (wave.depth[to] ?? 0) - 1 <= wave.step
    && (wave.depth[from] === 0 || wave.changed.has(from))) : []
  return (
    <div className="demo-graph">
      <div className="demo-graph-canvas" role="group"
        aria-label="Lineage graph. Sources at the top feed tool runs, which feed the two saved reports at the bottom.">
        <svg className="demo-graph-svg" viewBox={`0 0 ${GRAPH_W} ${GRAPH_H}`} aria-hidden focusable="false">
          {EDGES.map(({ from, to }) => (
            <path key={`${from}>${to}`} d={edgePath(from, to)} className={`demo-edge is-${edgeTone(display(from), display(to))}`} />
          ))}
          {wave && inked.map(({ from, to }) => (
            <motion.path key={`${wave.id}:${from}>${to}`} d={edgePath(from, to)}
              className={`demo-ink is-${inkTone(next[to])}`}
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
              transition={{ duration: 0.28, ease: [0.65, 0, 0.35, 1] }} />
          ))}
        </svg>
        {SLOTS.map(def => (
          <NodeButton key={def.slot} node={display(def.slot)} selected={selected === def.slot}
            origin={origin === def.slot} onSelect={onSelect} layout="canvas" />
        ))}
      </div>

      <div className="demo-graph-list">
        {LAYERS.map(({ layer, title }) => (
          <div className="demo-layer" key={layer}>
            <h4 className="demo-layer-title">{title}</h4>
            <ul>
              {SLOTS.filter(def => def.layer === layer).map(def => (
                <li key={def.slot}>
                  <NodeButton node={display(def.slot)} selected={selected === def.slot}
                    origin={origin === def.slot} onSelect={onSelect} layout="row" />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <ul className="demo-legend" aria-label="Legend">
        <li><span className="demo-legend-mark is-receipt" aria-hidden />Tool run with a recorded receipt</li>
        <li><span className="demo-legend-mark is-current" aria-hidden />Current</li>
        <li><span className="demo-legend-mark is-stale" aria-hidden />Needs refresh, value withheld</li>
        <li><span className="demo-legend-mark is-blocked" aria-hidden />Blocked by a removed source</li>
      </ul>
    </div>
  )
}
