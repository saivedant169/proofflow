import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { motion, useInView, useReducedMotion } from 'motion/react'
import { Play } from 'lucide-react'
import { Button, Source } from '../../components/ui'
import { repoFile } from '../../content/facts'
import { COMPONENTS, LINKS, NARROW, TRACE, WIDE, type CompId, type Component, type Layout } from './system'
import { edgeGeometry, reversePath } from './geometry'
import { useNarrow } from './useNarrow'

const HOP_MS = 1900
const SEGMENT_S = 0.55

function linkPath(layout: Layout, from: CompId, to: CompId): string | null {
  const direct = LINKS.find(l => l.from === from && l.to === to)
  const reverse = direct ? undefined : LINKS.find(l => l.from === to && l.to === from)
  const link = direct ?? reverse
  if (!link) return null
  const g = edgeGeometry(layout.nodes[link.from], layout.nodes[link.to], layout.axis, layout.narrow ? undefined : link.sides)
  return direct ? g.d : reversePath(g.d)
}

export function SystemDiagram() {
  const narrow = useNarrow()
  const layout = narrow ? NARROW : WIDE
  const reduce = useReducedMotion() ?? false
  const [selected, setSelected] = useState<CompId>('runtime')
  const [hop, setHop] = useState<number | null>(null)
  const [run, setRun] = useState(0)
  const figureRef = useRef<HTMLElement>(null)
  const inView = useInView(figureRef, { once: true, amount: 0.35 })
  const uid = useId().replace(/:/g, '')

  // Play the trace once when the diagram first comes into view (not with reduced motion).
  useEffect(() => {
    if (inView && !reduce) {
      setHop(0)
      setRun(r => r + 1)
    }
  }, [inView, reduce])

  // Advance one hop at a time; finish by clearing the highlight.
  useEffect(() => {
    if (hop === null) return
    const t = window.setTimeout(() => setHop(h => (h === null || h >= TRACE.length - 1 ? null : h + 1)), HOP_MS)
    return () => window.clearTimeout(t)
  }, [hop, run])

  const replay = () => { setHop(0); setRun(r => r + 1) }
  const active = hop === null ? null : TRACE[hop]
  const activeNodes = new Set(active?.segments.flat() ?? [])
  const comp = COMPONENTS.find(c => c.id === selected)!

  const onNodeKey = (id: CompId) => (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(id) }
  }

  return (
    <figure className="arch-figure panel" ref={figureRef}>
      <div className="arch-figure-head">
        <p className="arch-hint">Select a component to see what it does and what it never does.</p>
        <Button variant="secondary" onClick={replay} icon={<Play aria-hidden size={16} />}>
          {hop === null ? 'Replay request trace' : 'Restart trace'}
        </Button>
      </div>

      <div className="arch-canvas">
        <svg className={`arch-svg ${narrow ? 'arch-svg--narrow' : ''}`} viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="group" aria-labelledby={`arch-svg-title-${uid}`}>
          <title id={`arch-svg-title-${uid}`}>
            ProofFlow system diagram. Browser to FastAPI service; MCP host to MCP server; Python and CLI directly to the runtime.
            FastAPI and the MCP server call the ProofFlow runtime, which uses registered tools, the artifact store and HydraDB.
          </title>

          {LINKS.map(link => {
            const g = edgeGeometry(layout.nodes[link.from], layout.nodes[link.to], layout.axis, narrow ? undefined : link.sides)
            return (
              <g key={`${link.from}-${link.to}`}>
                <path d={g.d} className="arch-link" />
                {!narrow && link.label && (
                  <text className="arch-link-label" x={g.mid.x} y={g.mid.y - 8} textAnchor="middle">{link.label}</text>
                )}
              </g>
            )
          })}

          {active && active.segments.map(([from, to], i) => {
            const d = linkPath(layout, from, to)
            if (!d) return null
            return (
              <motion.path key={`${run}-${hop}-${i}-${narrow}`} d={d} className={`arch-pulse arch-pulse--${active.tone}`}
                initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }}
                transition={{ duration: SEGMENT_S, delay: i * SEGMENT_S, ease: 'easeInOut' }} />
            )
          })}

          {COMPONENTS.map(c => (
            <NodeView key={c.id} comp={c} layout={layout} selected={selected === c.id}
              traced={activeNodes.has(c.id) ? active!.tone : null}
              onSelect={() => setSelected(c.id)} onKey={onNodeKey(c.id)} />
          ))}
        </svg>
      </div>

      <div className="arch-below">
        <Inspector comp={comp} />
        <div className="arch-trace">
          <h3 className="arch-sub-title">Trace: one correction, end to end</h3>
          <ol className="arch-hops">
            {TRACE.map((h, i) => (
              <li key={h.label} className={`arch-hop arch-hop--${h.tone}`} aria-current={i === hop ? 'step' : undefined}>
                <span className="arch-hop-n figure" aria-hidden>{i + 1}</span>
                <span>
                  <strong>{h.label}</strong>
                  <span className="arch-hop-detail">{h.detail}</span>
                </span>
              </li>
            ))}
          </ol>
          <p className="sr-only" aria-live="polite">
            {active ? `Trace step ${hop! + 1} of ${TRACE.length}: ${active.label}. ${active.detail}` : ''}
          </p>
          <p className="arch-source-row">
            <Source path="docs/API_CONTRACT.md" />
            <Source path="README.md" label="README.md (four tools on refresh)" />
          </p>
        </div>
      </div>
    </figure>
  )
}

function NodeView({ comp, layout, selected, traced, onSelect, onKey }: {
  comp: Component; layout: Layout; selected: boolean; traced: 'stale' | 'fresh' | null
  onSelect: () => void; onKey: (e: KeyboardEvent) => void
}) {
  const box = layout.nodes[comp.id]
  const narrow = layout.narrow
  const x0 = box.x - box.w / 2
  const y0 = box.y - box.h / 2
  const title = narrow ? comp.short ?? comp.title : comp.title
  const sub = narrow ? comp.narrowSub ?? comp.sub : comp.sub
  const showExtra = !narrow && comp.extra
  const tx = narrow ? box.w / 2 : 16
  const anchor = narrow ? 'middle' : 'start'
  const titleY = showExtra ? box.h / 2 - 12 : box.h / 2 - 3
  return (
    <g className={`arch-node arch-node--${comp.layer} ${selected ? 'is-selected' : ''} ${traced ? `is-traced is-traced--${traced}` : ''}`}
      transform={`translate(${x0} ${y0})`} role="button" tabIndex={0} aria-pressed={selected}
      aria-label={`${comp.title}, ${comp.sub}`} onClick={onSelect} onKeyDown={onKey}>
      <rect className="arch-ring" x={-5} y={-5} width={box.w + 10} height={box.h + 10} rx={10} />
      <rect className="arch-box" width={box.w} height={box.h} rx={6} />
      <text className="arch-title" x={tx} y={titleY} textAnchor={anchor}>{title}</text>
      <text className={comp.subIsCode && !(narrow && comp.narrowSub) ? 'arch-code' : 'arch-sub'} x={tx} y={titleY + (narrow ? 17 : 21)} textAnchor={anchor}>{sub}</text>
      {showExtra && <text className="arch-sub" x={tx} y={titleY + 42} textAnchor={anchor}>{comp.extra}</text>}
    </g>
  )
}

function Inspector({ comp }: { comp: Component }) {
  return (
    <aside className="arch-inspector" aria-live="polite" aria-label="Selected component">
      <h3 className="arch-inspector-title">{comp.title}</h3>
      <p className="arch-role">{comp.role}</p>
      <p className="arch-never"><span className="arch-never-label">Never</span>{comp.never}</p>
      {comp.note && <p className="arch-note">{comp.note}</p>}
      <ul className="arch-files" aria-label="Files">
        {comp.files.map(f => (
          <li key={f}><a href={repoFile(f)} target="_blank" rel="noreferrer"><code>{f}</code><span className="sr-only"> (opens in a new tab)</span></a></li>
        ))}
      </ul>
      {comp.sources && (
        <p className="arch-source-row">{comp.sources.map(s => <Source key={s} path={s} />)}</p>
      )}
    </aside>
  )
}
