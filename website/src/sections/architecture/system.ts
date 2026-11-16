/**
 * Components of the running system, read from the code:
 * proofflow/api.py, proofflow/mcp_server.py, proofflow/runtime.py, proofflow/analytics.py,
 * proofflow/artifacts.py, proofflow/graph.py, docker-compose.yml, compose.app.yml.
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
  narrowSub?: string
  subIsCode?: boolean
  /** Second line, wide layout only. */
  extra?: string
  role: string
  never: string
  note?: string
  files: string[]
  sources?: string[]
}

export const COMPONENTS: Component[] = [
  {
    id: 'browser', layer: 'client', title: 'Browser', sub: 'React app', narrowSub: 'React',
    role: 'Shows the reports, each claim’s state and the native evidence paths. Every calculation runs on the server.',
    never: 'No API, model or HydraDB keys reach the browser.',
    files: ['frontend/src/App.tsx'], sources: ['docs/API_CONTRACT.md'],
  },
  {
    id: 'mcp', layer: 'client', title: 'MCP host', sub: 'your agent', narrowSub: 'stdio',
    role: 'Your agent host runs its own model, chooses the plan and calls ProofFlow’s five tools over stdio.',
    never: 'ProofFlow never calls a model. The host’s model identity, usage and cost are not verified by ProofFlow.',
    note: 'The hosted CSV connector is the other route: a local script that calls the FastAPI service over HTTPS.',
    files: ['docs/AGENT_QUICKSTART.md'], sources: ['README.md'],
  },
  {
    id: 'cli', layer: 'client', title: 'Python / CLI', sub: 'ProofFlowRuntime', narrowSub: 'Python', subIsCode: true,
    role: 'Python integrations and the CSV importer call the runtime directly, with the same registered tools.',
    never: 'Imports are validated before any write and bounded to 1 MiB and 1,000 rows.',
    files: ['scripts/import_csv.py', 'proofflow/importing.py'], sources: ['README.md'],
  },
  {
    id: 'api', layer: 'interface', title: 'FastAPI service', short: 'FastAPI', sub: 'api.py', subIsCode: true,
    role: 'Same-origin JSON API with isolated browser sessions: 16 at most by default, each expiring after one idle hour.',
    never: 'Never serves a fallback answer. HydraDB failures return 503, missing evidence returns 409.',
    files: ['proofflow/api.py'], sources: ['docs/DEPLOYMENT.md'],
  },
  {
    id: 'mcpserver', layer: 'interface', title: 'MCP server', sub: 'mcp_server.py', subIsCode: true,
    role: 'Five stdio tools over the same runtime: load a CSV, prepare typed handles, execute the host’s plan, inspect, refresh.',
    never: 'Accepts no paths, code, SQL, credentials or unregistered tools, and runs no model.',
    files: ['proofflow/mcp_server.py', 'proofflow/composition.py'],
  },
  {
    id: 'runtime', layer: 'core', title: 'ProofFlow runtime', sub: 'runtime.py', subIsCode: true,
    extra: 'receipts, currentness, refresh',
    role: 'Runs registered tools, writes receipts and lineage, checks currentness and refreshes stale work in dependency order.',
    never: 'Has no fallback graph. If HydraDB cannot answer, it raises an error instead of guessing.',
    files: ['proofflow/runtime.py', 'proofflow/models.py'],
  },
  {
    id: 'tools', layer: 'backend', title: 'Registered tools', short: 'Tools', sub: 'analytics.py', subIsCode: true,
    role: 'Seven deterministic tools: SQLite aggregations over explicit inputs, and currency math in integer cents with Decimal rates.',
    never: 'Tools never discover data or read files. No arbitrary code or SQL runs.',
    files: ['proofflow/analytics.py'],
  },
  {
    id: 'store', layer: 'backend', title: 'Artifact store', short: 'Store', sub: 'artifacts.py', subIsCode: true,
    role: 'Immutable JSON blobs named by their SHA-256 hash, plus a SQLite manifest of records and the current head of every source and tool.',
    never: 'It is not a traversal engine. A blob whose hash does not match is treated as missing evidence.',
    files: ['proofflow/artifacts.py'],
  },
  {
    id: 'hydra', layer: 'backend', title: 'HydraDB', sub: 'graph.py', subIsCode: true,
    role: 'Holds lineage nodes and edges and runs native ancestor and descendant traversal and path explanation.',
    never: 'No in-memory fallback. A graph deeper than 15 hops is refused, not truncated. The v0.4.0 image is pinned by digest and its ports bind to localhost.',
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

export interface Layout { width: number; height: number; axis: 'x' | 'y'; nodes: Record<CompId, Box>; narrow: boolean }

export const WIDE: Layout = {
  width: 1000,
  height: 440,
  axis: 'x',
  narrow: false,
  nodes: {
    browser: { x: 95, y: 80, w: 170, h: 66 },
    mcp: { x: 95, y: 220, w: 170, h: 66 },
    cli: { x: 95, y: 360, w: 170, h: 66 },
    api: { x: 340, y: 80, w: 180, h: 66 },
    mcpserver: { x: 340, y: 220, w: 180, h: 66 },
    runtime: { x: 600, y: 220, w: 200, h: 108 },
    tools: { x: 880, y: 80, w: 200, h: 66 },
    store: { x: 880, y: 220, w: 200, h: 66 },
    hydra: { x: 880, y: 360, w: 200, h: 66 },
  },
}

export const NARROW: Layout = {
  width: 330,
  height: 470,
  axis: 'y',
  narrow: true,
  nodes: {
    browser: { x: 57, y: 40, w: 102, h: 54 },
    mcp: { x: 165, y: 40, w: 102, h: 54 },
    cli: { x: 273, y: 40, w: 102, h: 54 },
    api: { x: 60, y: 158, w: 108, h: 54 },
    mcpserver: { x: 172, y: 158, w: 104, h: 54 },
    runtime: { x: 165, y: 290, w: 300, h: 70 },
    tools: { x: 57, y: 424, w: 102, h: 58 },
    store: { x: 165, y: 424, w: 102, h: 58 },
    hydra: { x: 273, y: 424, w: 102, h: 58 },
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
  { segments: [['browser', 'api']], tone: 'stale', label: 'A correction arrives', detail: 'POST /api/change sets EUR→USD to 1.20.' },
  { segments: [['api', 'runtime']], tone: 'stale', label: 'New source version', detail: 'set_source saves FX 1.20 and moves its head.' },
  { segments: [['runtime', 'hydra']], tone: 'stale', label: 'Find what depends on it', detail: 'Native descendant traversal returns every affected artifact, reports included.' },
  { segments: [['runtime', 'tools']], tone: 'fresh', label: 'Re-execute stale steps', detail: 'On POST /api/refresh, four tools run. Support is reused.' },
  { segments: [['runtime', 'hydra'], ['runtime', 'store']], tone: 'fresh', label: 'Record and commit', detail: 'New receipts and edges go to HydraDB, then hash-checked blobs and heads to the store.' },
  { segments: [['runtime', 'api'], ['api', 'browser']], tone: 'fresh', label: 'Reports are current', detail: 'Claims are served again with their new values.' },
]
