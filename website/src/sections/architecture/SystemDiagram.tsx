import { useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { animate, useInView, useReducedMotion } from 'motion/react'
import { Archive, Bot, Cpu, FileCode2, Globe, Network, Play, Plug, RotateCcw, Server, Terminal, Wrench, X, type LucideIcon } from 'lucide-react'
import { repoFile } from '../../content/facts'
import { COMPONENTS, LINKS, NARROW, TRACE, WIDE, type CompId, type Component, type Layout, type Tone } from './system'
import { edgeGeometry, reversePath } from './geometry'
import { useNarrow } from './useNarrow'

const HOP_MS = 1500
const SEGMENT_S = 0.5

const ICONS: Record<CompId, LucideIcon> = {
  browser: Globe, mcp: Bot, cli: Terminal, api: Server, mcpserver: Plug, runtime: Cpu, tools: Wrench, store: Archive, hydra: Network,
}

function linkPath(layout: Layout, from: CompId, to: CompId): string | null {
  const direct = LINKS.find(l => l.from === from && l.to === to)
  const reverse = direct ? undefined : LINKS.find(l => l.from === to && l.to === from)
  const link = direct ?? reverse
  if (!link) return null
  const g = edgeGeometry(layout.nodes[link.from], layout.nodes[link.to], layout.axis, layout.narrow ? undefined : link.sides)
  return direct ? g.d : reversePath(g.d)
}

const pct = (v: number, of: number) => `${(v / of) * 100}%`

export function SystemDiagram() {
  const narrow = useNarrow()
  const layout = narrow ? NARROW : WIDE
  const reduce = useReducedMotion() ?? false
  const [selected, setSelected] = useState<CompId | null>(null)
  const [hop, setHop] = useState<number | null>(null)
  const [run, setRun] = useState(0)
  const boardRef = useRef<HTMLDivElement>(null)
  const nodeRefs = useRef<Partial<Record<CompId, HTMLButtonElement | null>>>({})
  const skipFocusOpen = useRef(false)
  const inView = useInView(boardRef, { once: true, amount: 0.5 })
  const uid = useId().replace(/:/g, '')

  // Play the correction once when the diagram first comes into view (not with reduced motion).
  useEffect(() => {
    if (inView && !reduce) { setHop(0); setRun(r => r + 1) }
  }, [inView, reduce])

  // Advance one hop at a time; the last hop stays lit until the next play.
  useEffect(() => {
    if (hop === null || hop >= TRACE.length) return
    const t = window.setTimeout(() => setHop(h => (h === null ? null : h + 1)), HOP_MS)
    return () => window.clearTimeout(t)
  }, [hop, run])

  // Close the popover on a click outside it.
  useEffect(() => {
    if (!selected) return
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node
      if (!boardRef.current?.contains(t)) setSelected(null)
      else if (!(t as Element).closest?.('.arch-node, .arch-pop')) setSelected(null)
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [selected])

  const play = () => { setHop(0); setRun(r => r + 1) }
  const done = hop !== null && hop >= TRACE.length
  const activeIndex = hop === null ? null : Math.min(hop, TRACE.length - 1)
  const active = hop === null || done ? null : TRACE[hop]
  const activeNodes = new Set(active?.segments.flat() ?? [])

  const close = (id: CompId) => {
    setSelected(null)
    skipFocusOpen.current = true
    nodeRefs.current[id]?.focus()
    skipFocusOpen.current = false
  }
  const onKey = (id: CompId) => (e: KeyboardEvent) => {
    if (e.key === 'Escape' && selected) { e.preventDefault(); close(id) }
  }

  return (
    <figure className="arch-figure">
      <div className={`arch-board ${narrow ? 'arch-board--narrow' : ''}`} ref={boardRef}
        style={{ aspectRatio: `${layout.width} / ${layout.height}` } as CSSProperties}>
        <svg className="arch-svg" viewBox={`0 0 ${layout.width} ${layout.height}`} aria-hidden preserveAspectRatio="none">
          <defs>
            <radialGradient id={`arch-wash-${uid}`}>
              <stop offset="0" className="arch-wash-in" />
              <stop offset="1" className="arch-wash-out" />
            </radialGradient>
          </defs>
          <ellipse cx={layout.nodes.runtime.x} cy={layout.nodes.runtime.y} rx={narrow ? 190 : 300} ry={narrow ? 150 : 220}
            fill={`url(#arch-wash-${uid})`} />
          {layout.columns?.map(c => (
            <text key={c.label} className="arch-col" x={c.x} y={30} textAnchor="middle">{c.label}</text>
          ))}
          {LINKS.map(link => {
            const g = edgeGeometry(layout.nodes[link.from], layout.nodes[link.to], layout.axis, narrow ? undefined : link.sides)
            return (
              <g key={`${link.from}-${link.to}`}>
                <path d={g.d} className="arch-link" />
                {!narrow && link.label && (
                  <text className="arch-link-label" x={g.mid.x} y={g.mid.y - 9} textAnchor="middle">{link.label}</text>
                )}
              </g>
            )
          })}
          {active && active.segments.map(([from, to], i) => {
            const d = linkPath(layout, from, to)
            return d ? <Pulse key={`${run}-${hop}-${i}-${narrow}`} d={d} tone={active.tone} delay={i * SEGMENT_S} reduce={reduce} /> : null
          })}
        </svg>

        {COMPONENTS.map(c => (
          <NodeButton key={c.id} comp={c} layout={layout} uid={uid}
            open={selected === c.id}
            traced={activeNodes.has(c.id) ? active!.tone : null}
            refFn={el => { nodeRefs.current[c.id] = el }}
            onOpen={() => setSelected(c.id)}
            onToggle={() => setSelected(s => (s === c.id ? null : c.id))}
            onFocusOpen={() => { if (!skipFocusOpen.current) setSelected(c.id) }}
            onKey={onKey(c.id)}
            onClose={() => close(c.id)} />
        ))}
      </div>

      <figcaption className="arch-trace">
        <button type="button" className="arch-play" onClick={play}>
          {done ? <RotateCcw aria-hidden size={16} /> : <Play aria-hidden size={16} />}
          <span>{done ? 'Play again' : 'Play a correction'}</span>
        </button>
        <ol className="arch-hops" aria-label="Correction trace">
          {TRACE.map((h, i) => (
            <li key={h.label} className={`arch-hop arch-hop--${h.tone}`}
              data-state={activeIndex === null ? undefined : i < activeIndex || done ? 'done' : i === activeIndex ? 'now' : undefined}
              aria-current={!done && i === activeIndex ? 'step' : undefined}>
              <span className="sr-only">{h.label}</span>
            </li>
          ))}
        </ol>
        <p className="arch-hop-caption" aria-live="polite">
          {active ? (
            <>
              <span className="arch-hop-n figure">{String(hop! + 1).padStart(2, '0')}</span>
              <strong>{active.label}</strong>
              <span className="arch-hop-detail">{active.detail}</span>
            </>
          ) : done ? (
            <><span className="arch-hop-n figure is-fresh">06</span><strong>Reports current</strong><span className="arch-hop-detail">Four tools re-ran; support was reused.</span></>
          ) : (
            <span className="arch-hop-detail">Select any component.</span>
          )}
        </p>
      </figcaption>
    </figure>
  )
}

function Pulse({ d, tone, delay, reduce }: { d: string; tone: Tone; delay: number; reduce: boolean }) {
  const pathRef = useRef<SVGPathElement>(null)
  const headRef = useRef<SVGCircleElement>(null)
  useEffect(() => {
    const path = pathRef.current
    const head = headRef.current
    if (!path || !head) return
    const len = path.getTotalLength()
    const set = (t: number) => {
      path.style.strokeDashoffset = String(1 - t)
      const pt = path.getPointAtLength(t * len)
      head.setAttribute('cx', String(pt.x))
      head.setAttribute('cy', String(pt.y))
      head.style.opacity = t > 0 && t < 1 ? '1' : '0'
    }
    if (reduce) { set(1); return }
    set(0)
    const controls = animate(0, 1, { duration: SEGMENT_S, delay, ease: [0.65, 0, 0.35, 1], onUpdate: set })
    return () => controls.stop()
  }, [d, delay, reduce])
  return (
    <g>
      <path ref={pathRef} d={d} pathLength={1} className={`arch-pulse arch-pulse--${tone}`} style={{ strokeDasharray: '1 1', strokeDashoffset: 1 }} />
      <circle ref={headRef} r={6} className={`arch-dot arch-dot--${tone}`} style={{ opacity: 0 }} />
    </g>
  )
}

function NodeButton({ comp, layout, uid, open, traced, refFn, onOpen, onToggle, onFocusOpen, onKey, onClose }: {
  comp: Component; layout: Layout; uid: string; open: boolean; traced: Tone | null
  refFn: (el: HTMLButtonElement | null) => void
  onOpen: () => void; onToggle: () => void; onFocusOpen: () => void; onKey: (e: KeyboardEvent) => void; onClose: () => void
}) {
  const box = layout.nodes[comp.id]
  const Icon = ICONS[comp.id]
  const popId = `arch-pop-${uid}-${comp.id}`
  const W = layout.width
  const H = layout.height
  const style: CSSProperties = {
    left: pct(box.x - box.w / 2, W), top: pct(box.y - box.h / 2, H), width: pct(box.w, W), height: pct(box.h, H),
  }
  const title = layout.narrow ? comp.short ?? comp.title : comp.title

  // The popover opens beside the node, inside the board, never past its edges.
  const above = box.y > H * 0.5
  const align = layout.narrow ? 'full' : box.x < W * 0.3 ? 'start' : box.x > W * 0.7 ? 'end' : 'center'
  const pop: CSSProperties = {}
  if (above) pop.bottom = `calc(${pct(H - (box.y - box.h / 2), H)} + 10px)`
  else pop.top = `calc(${pct(box.y + box.h / 2, H)} + 10px)`
  if (align === 'start') pop.left = pct(box.x - box.w / 2, W)
  if (align === 'end') pop.right = pct(W - (box.x + box.w / 2), W)
  if (align === 'center') pop.left = pct(box.x, W)

  return (
    <>
      <button type="button" ref={refFn}
        className={`arch-node arch-node--${comp.layer} ${open ? 'is-open' : ''} ${traced ? `is-traced is-traced--${traced}` : ''}`}
        style={style} aria-expanded={open} aria-controls={open ? popId : undefined}
        onClick={() => (open ? onToggle() : onOpen())} onFocus={onFocusOpen} onKeyDown={onKey}>
        <Icon className="arch-node-icon" aria-hidden />
        <span className="arch-node-text">
          <span className="arch-node-title">{title}</span>
          <span className="arch-node-sub">{comp.sub}</span>
        </span>
      </button>
      {open && (
        <div id={popId} className={`arch-pop arch-pop--${align}`} style={pop} role="group" aria-label={`${comp.title} details`} onKeyDown={onKey}>
          <div className="arch-pop-head">
            <Icon className="arch-pop-icon" aria-hidden size={18} />
            <span className="arch-pop-title">{comp.title}</span>
            <button type="button" className="arch-pop-close" onClick={onClose} aria-label={`Close ${comp.title} details`}>
              <X aria-hidden size={16} />
            </button>
          </div>
          <p className="arch-pop-does">{comp.does}</p>
          <p className="arch-pop-never"><span>Never</span>{comp.never}</p>
          <ul className="arch-pop-files">
            {comp.files.map(f => (
              <li key={f}>
                <a href={repoFile(f)} target="_blank" rel="noreferrer">
                  <FileCode2 aria-hidden size={14} /><code>{f}</code><span className="sr-only"> (opens in a new tab)</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
