import { useRef } from 'react'
import { useInView, useReducedMotion } from 'motion/react'
import { ArrowUpRight, Coins, FileStack, Landmark, Plug, ScanSearch, Server, ShoppingCart } from 'lucide-react'
import { Source, StateTag } from '../../components/ui'
import { links } from '../../content/facts'
import { OF, STUDY_SOURCE, arm } from '../hero/data'
import './styles.css'

/*
 * Go-to-market in one glance: who runs recurring agent reports, what today's options cost them, how they
 * adopt ProofFlow, and the planned next wedge. No customers, prices or adoption numbers: none are measured
 * (docs/SUBMISSION_DRAFT.md: "Customer demand and time savings have not yet been measured").
 */

const TEAMS = [
  { name: 'Finance close', icon: Landmark },
  { name: 'Revenue & FX reporting', icon: Coins },
  { name: 'Commerce analytics', icon: ShoppingCart },
] as const

const full = arm('full')
const graph = arm('graph')
const dense = arm('dense')
const fullRatio = (full.inputTokens / graph.inputTokens).toFixed(1)

/** The hosted connector's six tools. Source: README.md, docs/AGENT_QUICKSTART.md. */
const TOOLS = [
  'create_csv_reports',
  'inspect_reports',
  'inspect_evidence',
  'update_csv',
  'refresh_reports',
  'export_current_reports',
] as const

export default function Who() {
  const reduce = useReducedMotion() ?? false
  const ref = useRef<HTMLOListElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.2 })

  return (
    <section id="who" className="section who-section" aria-labelledby="who-title">
      <div className="wrap">
        <header className="who-head">
          <h2 id="who-title" className="who-title">Built for numbers people act on.</h2>
          <p className="who-lede">
            Teams whose agents publish recurring figures pick today between costly re-reads and missed updates.
          </p>
        </header>

        <ol ref={ref} className="who-flow" data-run={inView || reduce ? 'true' : undefined}>
          <li className="who-step who-step--teams" style={{ ['--i' as string]: 0 }}>
            <h3 className="who-step-title"><span className="who-node" aria-hidden />Who runs it</h3>
            <ul className="who-teams">
              {TEAMS.map(t => (
                <li key={t.name}>
                  <span className="who-icon" aria-hidden><t.icon size={18} strokeWidth={2} /></span>
                  {t.name}
                </li>
              ))}
            </ul>
          </li>

          <li className="who-step who-step--pain" style={{ ['--i' as string]: 1 }}>
            <h3 className="who-step-title"><span className="who-node" aria-hidden />What it costs today</h3>
            <dl className="who-pains">
              <div className="who-pain">
                <dt><FileStack size={16} strokeWidth={2} aria-hidden />Re-read everything</dt>
                <dd className="who-pain-num figure">{fullRatio}×</dd>
                <dd className="who-pain-unit">ProofFlow’s input tokens</dd>
                <dd><StateTag state="unknown">Accurate but costly</StateTag></dd>
              </div>
              <div className="who-pain who-pain--miss">
                <dt><ScanSearch size={16} strokeWidth={2} aria-hidden />Vector search</dt>
                <dd className="who-pain-num figure">{OF - dense.correct}/{OF}</dd>
                <dd className="who-pain-unit">affected reports missed</dd>
                <dd><StateTag state="stale">Cheap but misses changes</StateTag></dd>
              </div>
            </dl>
            <Source path={STUDY_SOURCE} />
          </li>

          <li className="who-step who-step--adopt" style={{ ['--i' as string]: 2 }}>
            <h3 className="who-step-title"><span className="who-node" aria-hidden />How they adopt</h3>
            <div className="who-ways">
              <a className="who-way" href={links.connector} target="_blank" rel="noreferrer">
                <span className="who-way-head">
                  <span className="who-icon" aria-hidden><Plug size={18} strokeWidth={2} /></span>
                  <span className="who-way-title">Hosted MCP connector</span>
                  <ArrowUpRight className="who-way-go" size={18} strokeWidth={2} aria-hidden />
                </span>
                <span className="who-way-line">One download, six tools, any MCP agent host.</span>
                <span className="who-tools" aria-hidden>
                  {TOOLS.map(t => <code key={t}>{t}</code>)}
                </span>
                <span className="sr-only">(opens in a new tab)</span>
              </a>
              <a className="who-way" href="#run-locally">
                <span className="who-way-head">
                  <span className="who-icon" aria-hidden><Server size={18} strokeWidth={2} /></span>
                  <span className="who-way-title">Self-host</span>
                  <ArrowUpRight className="who-way-go" size={18} strokeWidth={2} aria-hidden />
                </span>
                <span className="who-way-line">Docker Compose runs the app beside pinned HydraDB OSS.</span>
                <span className="who-tools" aria-hidden><code>docker-compose.yml</code><code>hydradb:0.4.0</code></span>
              </a>
            </div>
            <span className="who-sources">
              <Source path="docs/AGENT_QUICKSTART.md" />
              <Source path="README.md" label="README.md (Run locally)" />
            </span>
          </li>
        </ol>

        <div className="who-next" aria-labelledby="who-next-title" role="group">
          <div className="who-next-head">
            <h3 id="who-next-title" className="who-step-title">Next wedge</h3>
            <span className="who-plan-tag">Roadmap, not shipped</span>
          </div>
          <ol className="who-next-chain">
            <li className="is-shipped"><span className="who-chain-mark" aria-hidden />CSV revenue reports<span className="who-chain-note">today</span></li>
            <li className="is-planned"><span className="who-chain-mark" aria-hidden />More registered tools<span className="who-chain-note">planned</span></li>
            <li className="is-planned"><span className="who-chain-mark" aria-hidden />More data sources<span className="who-chain-note">planned</span></li>
          </ol>
        </div>
      </div>
    </section>
  )
}
