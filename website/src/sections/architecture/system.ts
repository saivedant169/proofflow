/**
 * Components of the running system, read from the code:
 * proofflow/api.py, proofflow/mcp_server.py, proofflow/runtime.py, proofflow/analytics.py,
 * proofflow/artifacts.py, proofflow/graph.py, docker-compose.yml, compose.app.yml.
 * "does" stays at twelve words or fewer, "never" at eight or fewer; the long form is in the files.
 */
import type { Box, Side } from './geometry'

export type CompId = 'browser' | 'mcp' | 'cli' | 'api' | 'mcpserver' | 'runtime' | 'tools' | 'store' | 'hydra'
export type Layer = 'client' | 'interface' | 'core' | 'backend'

export interface Component {
  id: CompId
  layer: Layer
  title: string
  /** Shorter title for the phone layout. */
  short?: string
  sub: string
  does: string
  never: string
  files: string[]
}

export const COMPONENTS: Component[] = [
  {
    id: 'browser', layer: 'client', title: 'Browser', sub: 'React app',
    does: 'Shows reports, claim states and evidence paths. Computes nothing.',
    never: 'No API, model or HydraDB keys.',
    files: ['frontend/src/App.tsx'],
  },
  {
    id: 'mcp', layer: 'client', title: 'MCP host', sub: 'your agent',
    does: 'Your agent runs its own model, plans, and calls five tools.',
    never: 'ProofFlow never calls a model.',
    files: ['docs/AGENT_QUICKSTART.md'],
  },
  {
    id: 'cli', layer: 'client', title: 'Python / CLI', short: 'Python', sub: 'ProofFlowRuntime',
    does: 'Integrations and the CSV importer call the runtime directly.',
    never: 'No write before validation; 1 MiB cap.',
    files: ['scripts/import_csv.py', 'proofflow/importing.py'],
  },
  {
    id: 'api', layer: 'interface', title: 'FastAPI service', short: 'FastAPI', sub: 'api.py',
    does: 'Same-origin JSON API with isolated, expiring browser sessions.',
    never: 'No fallback answer: 503 or 409.',
    files: ['proofflow/api.py'],
  },
  {
    id: 'mcpserver', layer: 'interface', title: 'MCP server', short: 'MCP server', sub: 'mcp_server.py',
    does: 'Five stdio tools over the same runtime.',
    never: 'No paths, code, SQL, credentials or model.',
    files: ['proofflow/mcp_server.py', 'proofflow/composition.py'],
  },
  {
    id: 'runtime', layer: 'core', title: 'ProofFlow runtime', short: 'ProofFlow runtime', sub: 'runtime.py',
    does: 'Runs tools, writes receipts, checks currentness, refreshes stale work in order.',
    never: 'No fallback graph; errors instead of guessing.',
    files: ['proofflow/runtime.py', 'proofflow/models.py'],
  },
  {
    id: 'tools', layer: 'backend', title: 'Registered tools', short: 'Tools', sub: 'analytics.py',
    does: 'Seven deterministic tools: SQLite aggregations and integer-cent currency math.',
    never: 'Never discover data or run arbitrary code.',
    files: ['proofflow/analytics.py'],
  },
  {
    id: 'store', layer: 'backend', title: 'Artifact store', short: 'Store', sub: 'artifacts.py',
    does: 'Immutable SHA-256-named JSON blobs plus a SQLite manifest of heads.',
    never: 'A hash mismatch counts as missing evidence.',
    files: ['proofflow/artifacts.py'],
  },
  {
    id: 'hydra', layer: 'backend', title: 'HydraDB', sub: 'graph.py',
    does: 'Holds the lineage; native traversal returns exactly the affected context.',
    never: 'No in-memory fallback; over 15 hops refused.',
    files: ['proofflow/graph.py', 'docker-compose.yml'],
  },
]

export interface Link { from: CompId; to: CompId; label?: string; sides?: [Side, Side] }

export const LINKS: Link[] = [
  { from: 'browser', to: 'api', label: 'HTTP JSON' },
  { from: 'mcp', to: 'mcpserver', label: 'stdio' },
  { from: 'cli', to: 'runtime', label: 'Python', sides: ['right', 'bottom'] },
  { from: 'api', to: 'runtime' },
  { from: 'mcpserver', to: 'runtime' },
  { from: 'runtime', to: 'tools' },
  { from: 'runtime', to: 'store' },
  { from: 'runtime', to: 'hydra' },
]

export interface Layout {
  width: number; height: number; axis: 'x' | 'y'; narrow: boolean
  nodes: Record<CompId, Box>
  columns?: { x: number; label: string }[]
}

export const WIDE: Layout = {
  width: 1000,
  height: 470,
  axis: 'x',
  narrow: false,
  columns: [
    { x: 95, label: 'Clients' },
    { x: 340, label: 'Interfaces' },
    { x: 600, label: 'Core' },
    { x: 880, label: 'Backends' },
  ],
  nodes: {
    browser: { x: 95, y: 112, w: 172, h: 70 },
    mcp: { x: 95, y: 252, w: 172, h: 70 },
    cli: { x: 95, y: 392, w: 172, h: 70 },
    api: { x: 340, y: 112, w: 182, h: 70 },
    mcpserver: { x: 340, y: 252, w: 182, h: 70 },
    runtime: { x: 600, y: 252, w: 232, h: 112 },
    tools: { x: 880, y: 112, w: 196, h: 70 },
    store: { x: 880, y: 252, w: 196, h: 70 },
    hydra: { x: 880, y: 392, w: 196, h: 70 },
  },
}

export const NARROW: Layout = {
  width: 340,
  height: 520,
  axis: 'y',
  narrow: true,
  nodes: {
    browser: { x: 58, y: 40, w: 106, h: 62 },
    mcp: { x: 170, y: 40, w: 106, h: 62 },
    cli: { x: 282, y: 40, w: 106, h: 62 },
    api: { x: 60, y: 176, w: 112, h: 60 },
    mcpserver: { x: 178, y: 176, w: 112, h: 60 },
    runtime: { x: 170, y: 318, w: 330, h: 80 },
    tools: { x: 58, y: 468, w: 106, h: 66 },
    store: { x: 170, y: 468, w: 106, h: 66 },
    hydra: { x: 282, y: 468, w: 106, h: 66 },
  },
}

export type Tone = 'stale' | 'fresh'

export interface Hop {
  segments: [CompId, CompId][]
  label: string
  detail: string
  /** The change signal travels in orange; the refresh re-inks in mint. */
  tone: Tone
}

/** A correction followed by a refresh, as the guided sample performs it (README.md, docs/API_CONTRACT.md). */
export const TRACE: Hop[] = [
  { segments: [['browser', 'api']], tone: 'stale', label: 'Correction arrives', detail: 'POST /api/change sets EUR→USD to 1.20.' },
  { segments: [['api', 'runtime']], tone: 'stale', label: 'New source version', detail: 'set_source saves FX 1.20 and moves its head.' },
  { segments: [['runtime', 'hydra']], tone: 'stale', label: 'Find descendants', detail: 'Native HydraDB traversal returns every affected artifact.' },
  { segments: [['runtime', 'tools']], tone: 'fresh', label: 'Re-run stale tools', detail: 'POST /api/refresh: four tools run, support is reused.' },
  { segments: [['runtime', 'hydra'], ['runtime', 'store']], tone: 'fresh', label: 'Record and commit', detail: 'Receipts and edges to HydraDB, then hash-checked blobs and heads.' },
  { segments: [['runtime', 'api'], ['api', 'browser']], tone: 'fresh', label: 'Reports current', detail: 'Claims are served again with their new values.' },
]
