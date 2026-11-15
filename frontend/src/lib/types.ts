export type Currentness = 'current' | 'stale' | 'unknown';
export type JSONValue = string | number | boolean | null | JSONValue[] | { [key: string]: JSONValue };
export type JSONObject = { [key: string]: JSONValue };

export interface Claim {
  key: string;
  label: string;
  unit: string;
  /** Current value only. Stale and unknown claims always contain null here. */
  value: JSONValue;
  /** Historical value; never render this as a current answer. */
  saved_value: JSONValue;
  state: Currentness;
  artifact_id: string;
  path: (string | number)[];
  reasons: JSONObject[];
}

export interface Report {
  key: string;
  id: string;
  title: string;
  run_id: string;
  state: Currentness;
  claims: Claim[];
}

export type SourceName = 'orders' | 'refunds' | 'fx' | 'tickets';

export interface SourceSnapshot {
  name: SourceName;
  id: string | null;
  content_hash: string | null;
  removed: boolean;
  summary: JSONObject;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: string;
  logical_id: string;
  state: Currentness;
  current_head: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface Execution {
  id: string;
  tool: string;
  run_id: string;
  status: string;
  elapsed_ms: number;
  inputs: Record<string, string>;
  output_id: string | null;
  created_at?: string;
  params?: JSONObject;
}

export interface ChangeRecord {
  kind: SourceChange['kind'] | 'csv';
  label: string;
  previous_source_id: string | null;
  current_source_id: string | null;
  timestamp: string;
}

export interface AffectedArtifact {
  id: string;
  logical_id: string;
  title: string;
  kind: string;
}

export interface ToolCall {
  tool: string;
  status: string;
  elapsed_ms: number;
  output_id: string | null;
}

export interface RefreshSummary {
  executed_count: number;
  reused_count: number;
  executed_artifact_ids: string[];
  reused_artifact_ids: string[];
  elapsed_ms: number;
  tool_calls: ToolCall[];
  numeric_parity: boolean | null;
  unchanged_support: boolean;
  graph_queries: number;
}

export interface WorkspaceDataset {
  label: string;
  sources: SourceSnapshot[];
}

export type CurrencyCode = 'USD' | 'EUR' | 'GBP';

export interface ImportedDataset extends WorkspaceDataset {
  selected_region: string;
  regions: string[];
  currencies: CurrencyCode[];
  row_count: number;
  source_csv_sha256: string;
}

/** Calculations performed for validation are separate from published runtime calls. */
export interface CalculationAccounting {
  preflight_calculation_count: number;
  recorded_tool_call_count: number;
  verification_calculation_count: number;
  total_calculation_count: number;
}

export interface ImportRequest {
  csv_text: string;
  /** Non-USD rates must be explicit; the client never supplies inferred values. */
  rates?: Partial<Record<CurrencyCode, string>>;
  region?: string;
}

export interface ImportExportRequest {
  generation: string;
  report_ids: { company: string; region: string };
}

export interface ImportExport {
  filename: 'proofflow-current-reports.txt';
  media_type: 'text/plain;charset=utf-8';
  checked_at: string;
  content: string;
}

export interface ImportPreview {
  valid: true;
  persisted: false;
  content_sha256: string;
  row_count: number;
  regions: string[];
  currencies: CurrencyCode[];
  selected_region: string;
  rates: Partial<Record<CurrencyCode, string>>;
  supported_ticket_regions: string[];
  preflight_calculation_count: number;
  recorded_tool_calls: 0;
  accounting: CalculationAccounting;
}

export interface ImportOperation extends CalculationAccounting {
  kind: 'create' | 'update' | 'refresh' | 'verify';
  changed_source_count: number;
  noop: boolean;
  elapsed_ms: number;
  tool_calls: ToolCall[];
}

interface WorkspaceBase {
  session_id: string;
  generation: string;
  created_at: string;
  backend: { engine: string; native_queries: number; fallback: false };
  dataset: WorkspaceDataset;
  reports: Report[];
  impact: {
    change: ChangeRecord | null;
    affected_artifacts: AffectedArtifact[];
    changed_source_ids: string[];
  };
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  executions: Execution[];
  last_refresh: RefreshSummary | null;
  notices: string[];
}

export interface GuidedWorkspaceState extends WorkspaceBase {
  mode: 'guided_real_execution';
}

export interface ImportedWorkspaceState extends WorkspaceBase {
  mode: 'guided_csv_import';
  dataset: ImportedDataset;
  last_operation: ImportOperation;
  /** A failed source publication must be repaired by a successful CSV update. */
  incomplete_update: boolean;
}

export type WorkspaceState = GuidedWorkspaceState | ImportedWorkspaceState;

export type SourceChange =
  | { kind: 'fx'; value: string }
  | { kind: 'order'; delta_cents: number }
  | { kind: 'refund'; delta_cents: number }
  | { kind: 'support'; count: number }
  | { kind: 'remove'; source: SourceName };

export interface Verification {
  passed: boolean;
  reports: {
    id: string;
    title: string;
    state: Currentness;
    numeric_match: boolean | null;
    error: string | JSONObject | null;
  }[];
  scope: string;
}

export interface ImportVerification extends Verification {
  accounting: ImportOperation;
}

export interface ArtifactEvidence {
  id: string;
  kind: string;
  logical_id: string;
  content_hash: string;
  created_at: string;
  metadata: JSONObject;
  /** Full historical stored artifact, not a claim of currentness. */
  saved_value: JSONValue;
  state: Currentness;
}

export interface EvidencePath {
  source_id: string;
  target_id: string;
  nodes: { id: string; label: string; kind: string }[];
  edges: GraphEdge[];
}

export interface Evidence {
  artifact: ArtifactEvidence;
  receipt: JSONObject | null;
  paths: EvidencePath[];
}

export interface Health {
  status: 'ok';
  backend: string;
}
