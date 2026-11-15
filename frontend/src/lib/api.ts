import type {
  Evidence, Health, ImportedWorkspaceState, ImportPreview, ImportRequest,
  ImportVerification, SourceChange, Verification, WorkspaceState,
} from './types';

export class APIError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status = 0, code = 'network_error') {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = { signal?: AbortSignal };
type RecordValue = Record<string, unknown>;

function isRecord(value: unknown): value is RecordValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isState(value: unknown): boolean {
  return value === 'current' || value === 'stale' || value === 'unknown';
}

function malformed(): never {
  throw new APIError('The server returned incomplete evidence. No current result was accepted.', 502, 'invalid_response');
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string');
}

function accounting(value: unknown): void {
  if (!isRecord(value) || !isCount(value.preflight_calculation_count)
    || !isCount(value.recorded_tool_call_count) || !isCount(value.verification_calculation_count)
    || !isCount(value.total_calculation_count)
    || value.total_calculation_count !== value.preflight_calculation_count
      + value.recorded_tool_call_count + value.verification_calculation_count) malformed();
}

function importOperation(value: unknown): void {
  accounting(value);
  if (!isRecord(value) || !['create', 'update', 'refresh', 'verify'].includes(String(value.kind))
    || !isCount(value.changed_source_count) || typeof value.noop !== 'boolean'
    || typeof value.elapsed_ms !== 'number' || !Number.isFinite(value.elapsed_ms) || value.elapsed_ms < 0
    || !Array.isArray(value.tool_calls)) malformed();
}

/** Check the serving invariant at the UI boundary; never turn missing evidence into mock data. */
function workspace(value: unknown): WorkspaceState {
  if (!isRecord(value) || typeof value.session_id !== 'string' || typeof value.generation !== 'string'
    || !['guided_real_execution', 'guided_csv_import'].includes(String(value.mode))
    || !isRecord(value.backend) || value.backend.fallback !== false
    || !isRecord(value.dataset) || !Array.isArray(value.dataset.sources) || !Array.isArray(value.reports)
    || !isRecord(value.impact) || !Array.isArray(value.impact.affected_artifacts)
    || !Array.isArray(value.impact.changed_source_ids) || !isRecord(value.graph)
    || !Array.isArray(value.graph.nodes) || !Array.isArray(value.graph.edges)
    || !Array.isArray(value.executions) || !Array.isArray(value.notices)) malformed();

  for (const report of value.reports) {
    if (!isRecord(report) || typeof report.id !== 'string' || !isState(report.state) || !Array.isArray(report.claims)) malformed();
    for (const claim of report.claims) {
      if (!isRecord(claim) || typeof claim.key !== 'string' || !isState(claim.state)
        || !('value' in claim) || !('saved_value' in claim) || !Array.isArray(claim.reasons)) malformed();
      if (claim.state !== 'current' && claim.value !== null) malformed();
      if (typeof claim.value === 'number' && !Number.isFinite(claim.value)) malformed();
    }
  }
  if (value.last_refresh !== null && (!isRecord(value.last_refresh)
    || typeof value.last_refresh.executed_count !== 'number'
    || !Array.isArray(value.last_refresh.tool_calls)
    || ![true, false, null].includes(value.last_refresh.numeric_parity as boolean | null))) malformed();
  if (value.mode === 'guided_csv_import') {
    if (typeof value.dataset.selected_region !== 'string' || !isStringArray(value.dataset.regions)
      || !isStringArray(value.dataset.currencies) || !isCount(value.dataset.row_count)
      || typeof value.dataset.source_csv_sha256 !== 'string' || typeof value.incomplete_update !== 'boolean') malformed();
    importOperation(value.last_operation);
  }
  return value as unknown as WorkspaceState;
}

function importedWorkspace(value: unknown): ImportedWorkspaceState {
  const state = workspace(value);
  if (state.mode !== 'guided_csv_import') malformed();
  return state;
}

async function request(path: string, method: 'GET' | 'POST', body?: unknown, options: RequestOptions = {}): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      signal: options.signal,
    });
  } catch (error) {
    // Preserve cancellation so an unmounted view does not announce a connection failure.
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new APIError('Could not reach ProofFlow. Reload the workspace to confirm its latest state.');
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new APIError('The server did not return JSON evidence. Please try again when the service is available.', response.status, 'invalid_response');
  }
  if (!response.ok) {
    const error = isRecord(payload) && isRecord(payload.error) ? payload.error : null;
    throw new APIError(
      error && typeof error.message === 'string' ? error.message : `ProofFlow could not complete this request (${response.status}).`,
      response.status,
      error && typeof error.code === 'string' ? error.code : 'request_failed',
    );
  }
  return payload;
}

export async function createSession(options?: RequestOptions): Promise<WorkspaceState> {
  return workspace(await request('/api/session', 'POST', {}, options));
}

export async function readState(options?: RequestOptions): Promise<WorkspaceState> {
  return workspace(await request('/api/state', 'GET', undefined, options));
}

export async function applyChange(change: SourceChange, options?: RequestOptions): Promise<WorkspaceState> {
  return workspace(await request('/api/change', 'POST', change, options));
}

export async function refresh(reportIds?: string[], options?: RequestOptions): Promise<WorkspaceState> {
  return workspace(await request('/api/refresh', 'POST', reportIds ? { report_ids: reportIds } : {}, options));
}

export async function reset(options?: RequestOptions): Promise<WorkspaceState> {
  return workspace(await request('/api/reset', 'POST', {}, options));
}

function verification(value: unknown): Verification {
  if (!isRecord(value) || typeof value.passed !== 'boolean' || !Array.isArray(value.reports)
    || typeof value.scope !== 'string') malformed();
  for (const report of value.reports) {
    if (!isRecord(report) || typeof report.id !== 'string' || !isState(report.state)
      || ![true, false, null].includes(report.numeric_match as boolean | null)) malformed();
  }
  return value as unknown as Verification;
}

export async function verify(options?: RequestOptions): Promise<Verification> {
  return verification(await request('/api/verify', 'POST', {}, options));
}

function evidence(value: unknown, artifactId: string): Evidence {
  if (!isRecord(value) || !isRecord(value.artifact) || value.artifact.id !== artifactId
    || !Array.isArray(value.paths) || !(value.receipt === null || isRecord(value.receipt))) malformed();
  return value as unknown as Evidence;
}

export async function readEvidence(artifactId: string, options?: RequestOptions): Promise<Evidence> {
  if (!artifactId) throw new APIError('Choose an artifact to inspect.', 400, 'missing_artifact');
  return evidence(await request(`/api/evidence/${encodeURIComponent(artifactId)}`, 'GET', undefined, options), artifactId);
}

export async function previewImport(input: ImportRequest, options?: RequestOptions): Promise<ImportPreview> {
  const value = await request('/api/import/preview', 'POST', input, options);
  if (!isRecord(value) || value.valid !== true || value.persisted !== false
    || typeof value.content_sha256 !== 'string' || !isCount(value.row_count)
    || !isStringArray(value.regions) || !isStringArray(value.currencies)
    || typeof value.selected_region !== 'string' || !isRecord(value.rates)
    || !Object.values(value.rates).every(rate => typeof rate === 'string')
    || !isStringArray(value.supported_ticket_regions) || !isCount(value.preflight_calculation_count)
    || value.recorded_tool_calls !== 0) malformed();
  accounting(value.accounting);
  if (!isRecord(value.accounting) || value.accounting.recorded_tool_call_count !== 0
    || value.accounting.verification_calculation_count !== 0
    || value.accounting.preflight_calculation_count !== value.preflight_calculation_count) malformed();
  return value as unknown as ImportPreview;
}

export async function createImport(input: ImportRequest, options?: RequestOptions): Promise<ImportedWorkspaceState> {
  return importedWorkspace(await request('/api/import/create', 'POST', input, options));
}

export async function readImportState(options?: RequestOptions): Promise<ImportedWorkspaceState> {
  return importedWorkspace(await request('/api/import/state', 'GET', undefined, options));
}

export async function updateImport(input: ImportRequest, options?: RequestOptions): Promise<ImportedWorkspaceState> {
  return importedWorkspace(await request('/api/import/update', 'POST', input, options));
}

export async function refreshImport(options?: RequestOptions): Promise<ImportedWorkspaceState> {
  return importedWorkspace(await request('/api/import/refresh', 'POST', {}, options));
}

export async function verifyImport(options?: RequestOptions): Promise<ImportVerification> {
  const value = await request('/api/import/verify', 'POST', {}, options);
  verification(value);
  if (!isRecord(value)) malformed();
  importOperation(value.accounting);
  if (!isRecord(value.accounting) || value.accounting.kind !== 'verify') malformed();
  return value as unknown as ImportVerification;
}

export async function readImportEvidence(artifactId: string, options?: RequestOptions): Promise<Evidence> {
  if (!artifactId) throw new APIError('Choose an artifact to inspect.', 400, 'missing_artifact');
  return evidence(await request(`/api/import/evidence/${encodeURIComponent(artifactId)}`, 'GET', undefined, options), artifactId);
}

export async function health(options?: RequestOptions): Promise<Health> {
  const value = await request('/health', 'GET', undefined, options);
  if (!isRecord(value) || value.status !== 'ok' || typeof value.backend !== 'string') malformed();
  return value as unknown as Health;
}

export const api = {
  createSession, readState, applyChange, refresh, reset, verify, readEvidence, health,
  previewImport, createImport, readImportState, updateImport, refreshImport, verifyImport, readImportEvidence,
};
