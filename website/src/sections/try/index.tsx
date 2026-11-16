import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { motion, useInView } from 'motion/react'
import { AppWindow, ArrowUpRight, FileArchive, FileCode2, Lock, Plug, ShieldCheck } from 'lucide-react'
import { Source } from '../../components/ui'
import { links } from '../../content/facts'
import AgentThreads from './AgentThreads'
import CopyCode, { type CommandSet } from './CopyCode'
import Footer from './Footer'
import './styles.css'

const COMMANDS: CommandSet[] = [
  {
    id: 'run',
    label: 'Run',
    lines: ['python3 scripts/init_local.py', 'docker compose -f docker-compose.yml -f compose.app.yml up -d --build'],
    note: 'then open http://127.0.0.1:18080',
  },
  {
    id: 'test',
    label: 'Test',
    lines: ['uv sync --frozen --extra test --extra benchmark --extra mcp', 'uv run pytest -q'],
    note: 'no model credentials needed',
  },
]

const MORE = [
  { label: 'Evidence ZIP', href: links.evidenceZip, icon: FileArchive, tip: 'Saved model study and an offline verifier', download: true },
  { label: 'Evidence page', href: links.publicEvidence, icon: ShieldCheck, tip: 'Public evidence and checksums' },
  { label: 'Connector script', href: links.connectorScript, icon: FileCode2, tip: 'Verify against its published checksum' },
  { label: 'Repository', href: links.repo, icon: Lock, tip: 'Private; opens for judges with approved access', badge: 'judge access' },
] as const

type TileProps = {
  index: number
  icon: ReactNode
  title: string
  line: string
  chip: ReactNode
  media: ReactNode
  onHover: (i: number | null) => void
}

function TileBody({ icon, title, line, chip, arrow = true }: Pick<TileProps, 'icon' | 'title' | 'line' | 'chip'> & { arrow?: boolean }) {
  return (
    <div className="try-tile-body">
      <span className="try-tile-icon" aria-hidden>{icon}</span>
      <div className="try-tile-text">
        <h3 className="try-tile-title">{title}</h3>
        <p className="try-tile-line">{line}</p>
      </div>
      <span className="try-tile-chip">{chip}</span>
      {arrow && <ArrowUpRight className="try-tile-go" size={20} strokeWidth={2} aria-hidden />}
    </div>
  )
}

function LinkTile({ href, index, onHover, media, ...body }: TileProps & { href: string }) {
  return (
    <a className="try-tile" href={href} target="_blank" rel="noreferrer"
      onMouseEnter={() => onHover(index)} onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(index)} onBlur={() => onHover(null)}>
      <div className="try-tile-media stage">{media}</div>
      <TileBody {...body} />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  )
}

/** One thread from the headline branching to each tile; the branch to the tile in hand lights up. */
function Branches({ hover, tiles }: { hover: number | null; tiles: RefObject<HTMLDivElement | null> }) {
  const ref = useRef<SVGSVGElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.6 })
  const [geo, setGeo] = useState<{ w: number; h: number; ends: number[] } | null>(null)

  useEffect(() => {
    const svg = ref.current
    const grid = tiles.current
    if (!svg || !grid) return
    const measure = () => {
      const box = svg.getBoundingClientRect()
      const ends = [...grid.children].map(c => {
        const r = c.getBoundingClientRect()
        return r.left + r.width / 2 - box.left
      })
      setGeo({ w: box.width, h: box.height, ends })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(svg)
    ro.observe(grid)
    return () => ro.disconnect()
  }, [tiles])

  return (
    <svg ref={ref} className="try-branches" aria-hidden focusable="false"
      viewBox={geo ? `0 0 ${geo.w} ${geo.h}` : undefined}>
      {geo && geo.ends.map((x, i) => {
        const cx = geo.w / 2
        const d = `M${cx} 0 C${cx} ${geo.h * 0.55} ${x} ${geo.h * 0.45} ${x} ${geo.h}`
        return (
          <g key={i} className={hover === i ? 'is-hot' : ''}>
            <motion.path d={d} className="try-branch"
              initial={{ pathLength: 0 }} animate={{ pathLength: inView ? 1 : 0 }}
              transition={{ duration: 0.9, delay: 0.12 * i, ease: [0.22, 1, 0.36, 1] }} />
            <path d={d} className="try-branch-hot" pathLength={1} />
            <circle cx={x} cy={geo.h - 1} r={3} className="try-branch-end" />
          </g>
        )
      })}
    </svg>
  )
}

export default function TryIt() {
  const [hover, setHover] = useState<number | null>(null)
  const [agentRun, setAgentRun] = useState<'idle' | 'a' | 'b'>('idle')
  const tilesRef = useRef<HTMLDivElement>(null)
  const tilesInView = useInView(tilesRef, { once: true, amount: 0.4 })

  useEffect(() => { if (tilesInView) setAgentRun(r => (r === 'idle' ? 'a' : r)) }, [tilesInView])

  const onHover = (i: number | null) => {
    setHover(i)
    if (i === 1) setAgentRun(r => (r === 'a' ? 'b' : 'a'))
  }

  return (
    <>
      <section id="try" className="section try-section" aria-labelledby="try-title">
        <div className="wrap">
          <header className="try-head">
            <h2 id="try-title" className="try-title">Try it in thirty seconds.</h2>
            <p className="try-lede">Open the live app or connect your own agent.</p>
          </header>

          <Branches hover={hover} tiles={tilesRef} />

          <div className="try-tiles" ref={tilesRef}>
            <LinkTile index={0} onHover={onHover} href={links.liveApp}
              icon={<AppWindow size={20} strokeWidth={2} />}
              title="Open the live app"
              line="Correct one rate. Watch 4 affected steps re-run."
              chip={<><span className="try-live-dot" aria-hidden />Live</>}
              media={
                <img className="try-shot" src={import.meta.env.BASE_URL + 'shots/workspace-refreshed-final.jpg'}
                  width={1536} height={1096} loading="lazy" decoding="async"
                  alt="The live ProofFlow workspace after a refresh: company revenue $5,755.00, current, beside the evidence graph." />
              } />

            <LinkTile index={1} onHover={onHover} href={links.connector}
              icon={<Plug size={20} strokeWidth={2} />}
              title="Connect your agent"
              line="Traverses dependencies, not similarity. No account needed."
              chip="6 MCP tools"
              media={<AgentThreads run={agentRun} />} />
          </div>

          <div className="try-local">
            <div className="try-local-text">
              <h3 className="try-local-title">Run it locally</h3>
              <ul className="try-reqs" aria-label="Requirements">
                <li>Docker</li>
                <li>Python 3</li>
              </ul>
            </div>
            <CopyCode label="Local commands" sets={COMMANDS} />
          </div>

          <ul className="try-more" aria-label="More resources">
            {MORE.map(m => (
              <li key={m.label}>
                <a href={m.href} className="try-more-link" data-tip={m.tip}
                  {...('download' in m ? {} : { target: '_blank', rel: 'noreferrer' })}>
                  <m.icon size={16} strokeWidth={2} aria-hidden />
                  <span>{m.label}</span>
                  {'badge' in m && <span className="try-more-badge">{m.badge}</span>}
                  <span className="sr-only">. {m.tip}.{'download' in m ? '' : ' Opens in a new tab.'}</span>
                </a>
              </li>
            ))}
          </ul>

          <p className="try-sources">
            <Source path="README.md" />
            <Source path="docs/AGENT_QUICKSTART.md" />
            <Source path="docs/PUBLIC_EVIDENCE.md" />
          </p>
        </div>
      </section>
      <Footer />
    </>
  )
}
