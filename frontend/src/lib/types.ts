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
  kind: SourceChange['kind'];
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

export interface WorkspaceState {
  session_id: string;
  generation: string;
  created_at: string;
  mode: 'guided_real_execution';
  backend: { engine: string; native_queries: number; fallback: false };
  dataset: { label: string; sources: SourceSnapshot[] };
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
