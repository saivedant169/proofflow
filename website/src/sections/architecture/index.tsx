import { useId, useState } from 'react'
import { ChevronDown, Code2, ShieldCheck } from 'lucide-react'
import { repoFile } from '../../content/facts'
import { Tip } from '../how/Tip'
import { SystemDiagram } from './SystemDiagram'
import { CodeSample } from './CodeSample'
import './styles.css'

/** Fail-closed guarantees. Label ≤ 4 words; the detail lives in the tooltip. */
const FAIL_CLOSED = [
  {
    label: 'No fallback answers',
    tip: <>HydraDB unavailable: 503 <code>backend_unavailable</code>. Missing evidence: 409 <code>evidence_unavailable</code>. No in-memory graph fallback.</>,
  },
  {
    label: 'Stale is withheld',
    tip: <>Stale and unknown values are withheld. <code>saved_value</code> is history, never a current claim.</>,
  },
  {
    label: 'Hashes verified',
    tip: 'A stored blob whose hash does not match its record is treated as missing evidence.',
  },
  {
    label: 'Registered tools only',
    tip: 'Every value comes from a registered tool. No model-written code or SQL runs, and plans are validated before the first tool.',
  },
]

const MCP_TOOLS = [
  { name: 'load_csv', tip: 'Publishes your CSV as source versions and returns the artifacts it affects.' },
  { name: 'prepare', tip: 'Returns current typed handles, tool contracts, the plan schema and a snapshot token.' },
  { name: 'execute_plan', tip: 'Validates the host’s plan (at most 12 steps) against that snapshot (expires after ten minutes), runs it, and returns claims and the actual tool calls.' },
  { name: 'inspect', tip: 'Returns source versions, currentness, values and receipts. Stale values are withheld.' },
  { name: 'refresh', tip: 'Recomputes affected prerequisites, rebinds downstream inputs and returns replacement IDs.' },
]

const STACK = ['Python 3.11+', 'FastAPI', 'SQLite', 'HydraDB 0.4.0, pinned', 'React 19', 'Vite', 'Docker Compose', 'MCP SDK 2.3.0']

const SOURCES = [
  'README.md', 'docs/API_CONTRACT.md', 'docs/AGENT_QUICKSTART.md', 'proofflow/api.py', 'proofflow/runtime.py',
  'proofflow/mcp_server.py', 'proofflow/artifacts.py', 'pyproject.toml', 'docker-compose.yml', 'frontend/package.json',
]

export default function Architecture() {
  const [showCode, setShowCode] = useState(false)
  const codeId = `arch-code-${useId().replace(/:/g, '')}`
  return (
    <section id="architecture" className="section stage architecture-section" aria-labelledby="architecture-title">
      <div className="wrap">
        <header className="arch-head">
          <h2 className="section-title" id="architecture-title">Traverse the structure. Skip the re-read.</h2>
          <p className="section-lede">HydraDB holds the lineage, so agents pull exactly the affected path instead of re-reading everything.</p>
        </header>

        <SystemDiagram />

        <div className="arch-specs">
          <div className="arch-spec">
            <h3 className="arch-spec-title">Fails closed</h3>
            <ul className="arch-chips">
              {FAIL_CLOSED.map((f, i) => (
                <li key={f.label}>
                  <Tip className="arch-chip" tip={f.tip} align={i === 0 ? 'start' : 'center'}>
                    <ShieldCheck aria-hidden size={15} />{f.label}
                  </Tip>
                </li>
              ))}
            </ul>
          </div>
          <div className="arch-spec">
            <h3 className="arch-spec-title">Five MCP tools</h3>
            <ul className="arch-chips">
              {MCP_TOOLS.map(t => (
                <li key={t.name}><Tip className="arch-pill" tip={t.tip}>{t.name}</Tip></li>
              ))}
            </ul>
          </div>
          <div className="arch-spec">
            <h3 className="arch-spec-title">Stack</h3>
            <ul className="arch-stack">
              {STACK.map(s => <li key={s}>{s}</li>)}
            </ul>
          </div>
          <div className="arch-spec arch-spec--code">
            <h3 className="arch-spec-title">Runtime API</h3>
            <button type="button" className="arch-disclose" aria-expanded={showCode} aria-controls={codeId}
              onClick={() => setShowCode(s => !s)}>
              <Code2 aria-hidden size={16} />
              <span>{showCode ? 'Hide code' : 'Show code'}</span>
              <ChevronDown aria-hidden size={16} className="arch-disclose-chev" />
            </button>
          </div>
        </div>

        <div id={codeId} className="arch-code-wrap" hidden={!showCode}>
          {showCode && (
            <>
              <CodeSample />
              <p className="arch-code-note">
                Needs local HydraDB: <code>python3 scripts/init_local.py</code>, then <code>docker compose up -d</code>.
              </p>
            </>
          )}
        </div>

        <div className="arch-foot">
          <p className="arch-sources">
            <span>Sources</span>
            {SOURCES.map(s => <a key={s} href={repoFile(s)} target="_blank" rel="noreferrer"><code>{s}</code></a>)}
          </p>
        </div>
      </div>
    </section>
  )
}
