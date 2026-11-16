import type { ReactNode } from 'react'
import { SectionHead, Source } from '../../components/ui'
import { SystemDiagram } from './SystemDiagram'
import { CodeSample } from './CodeSample'
import './styles.css'

const FAIL_CLOSED: { text: ReactNode; source: string; label?: string }[] = [
  {
    text: 'Missing graph evidence, missing content or unsupported depth fails closed. There is no in-memory graph fallback.',
    source: 'README.md',
  },
  {
    text: <>When HydraDB is unavailable the API answers 503 <code>backend_unavailable</code>; missing evidence answers 409 <code>evidence_unavailable</code>. No fallback answer is served.</>,
    source: 'proofflow/api.py',
  },
  {
    text: <>Stale and unknown values are withheld. <code>saved_value</code> is history, never a current claim.</>,
    source: 'docs/AGENT_QUICKSTART.md',
  },
  {
    text: 'Registered tools calculate every value. No arbitrary model-generated code or SQL executes.',
    source: 'README.md',
  },
  {
    text: 'Plan validation rejects unknown handles, forward references, unsupported operations and mismatched claim units, before the first tool runs.',
    source: 'README.md',
    label: 'README.md, docs/COMPOSITION.md',
  },
  {
    text: 'A stored blob whose hash does not match its record is treated as missing evidence.',
    source: 'proofflow/artifacts.py',
  },
]

const MCP_TOOLS = [
  { name: 'load_csv', text: 'Publishes your CSV as source versions and returns the artifacts it affects.' },
  { name: 'prepare', text: 'Returns current typed handles, tool contracts, the plan schema and a snapshot token.' },
  { name: 'execute_plan', text: 'Validates the host’s plan against that snapshot, runs it, and returns claims and the actual tool calls.' },
  { name: 'inspect', text: 'Returns source versions, currentness, values and receipts. Stale values are withheld.' },
  { name: 'refresh', text: 'Recomputes affected prerequisites, rebinds downstream inputs and returns replacement IDs.' },
]

const STACK = ['Python 3.11+', 'FastAPI', 'SQLite', 'HydraDB 0.4.0, pinned by digest', 'React 19', 'Vite', 'Docker Compose', 'MCP SDK 2.3.0']

export default function Architecture() {
  return (
    <section id="architecture" className="section architecture-section" aria-labelledby="architecture-title">
      <div className="wrap">
        <SectionHead
          id="architecture-title"
          title="Small parts, strict boundaries"
          lede="One runtime records every tool run. HydraDB holds the lineage, a hash-checked store holds the content, and anything that cannot be verified is withheld."
        />

        <SystemDiagram />

        <div className="arch-split">
          <div className="arch-block">
            <h3 className="arch-block-title">Fails closed, by design</h3>
            <ul className="arch-rules">
              {FAIL_CLOSED.map((r, i) => (
                <li key={i}>
                  <p>{r.text}</p>
                  <Source path={r.source} label={r.label} />
                </li>
              ))}
            </ul>
          </div>

          <div className="arch-block">
            <h3 className="arch-block-title">Agent interface: five MCP tools</h3>
            <p className="arch-block-lede">
              The server runs no model. Your host chooses the plan: at most 12 steps, against a snapshot that expires after ten minutes.
            </p>
            <dl className="arch-tools">
              {MCP_TOOLS.map(t => (
                <div key={t.name} className="arch-tool">
                  <dt><code>{t.name}</code></dt>
                  <dd>{t.text}</dd>
                </div>
              ))}
            </dl>
            <p className="arch-source-row">
              <Source path="docs/AGENT_QUICKSTART.md" />
              <Source path="proofflow/mcp_server.py" />
            </p>
          </div>
        </div>

        <div className="arch-api">
          <div className="arch-api-text">
            <h3 className="arch-block-title">Runtime API</h3>
            <p>
              Python integrations use five calls around the registered tools: <code>set_source</code>, <code>execute</code>,{' '}
              <code>currentness</code>, <code>affected</code> and <code>refresh</code>.
            </p>
            <p className="soft arch-api-note">
              Needs the local HydraDB service: <code>python3 scripts/init_local.py</code>, then <code>docker compose up -d</code>.
            </p>
            <p className="arch-source-row">
              <Source path="proofflow/runtime.py" />
              <Source path="docs/AGENT_QUICKSTART.md" label="docs/AGENT_QUICKSTART.md (setup)" />
            </p>
          </div>
          <CodeSample />
        </div>

        <div className="arch-stack">
          <h3 className="arch-stack-title">Stack</h3>
          <ul className="arch-stack-list">
            {STACK.map(s => <li key={s}>{s}</li>)}
          </ul>
          <p className="arch-source-row">
            <Source path="pyproject.toml" />
            <Source path="proofflow/artifacts.py" label="proofflow/artifacts.py (SQLite)" />
            <Source path="docker-compose.yml" />
            <Source path="frontend/package.json" />
            <Source path="compose.app.yml" />
          </p>
        </div>
      </div>
    </section>
  )
}
