import type { Evidence, Health, SourceChange, Verification, WorkspaceState } from './types';

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

/** Check the serving invariant at the UI boundary; never turn missing evidence into mock data. */
function workspace(value: unknown): WorkspaceState {
  if (!isRecord(value) || typeof value.session_id !== 'string' || typeof value.generation !== 'string'
    || value.mode !== 'guided_real_execution' || !isRecord(value.backend) || value.backend.fallback !== false
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
  return value as unknown as WorkspaceState;
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
    throw new APIError('Could not reach ProofFlow. Your saved results have not been replaced.');
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

export async function verify(options?: RequestOptions): Promise<Verification> {
  const value = await request('/api/verify', 'POST', {}, options);
  if (!isRecord(value) || typeof value.passed !== 'boolean' || !Array.isArray(value.reports)
    || typeof value.scope !== 'string') malformed();
  for (const report of value.reports) {
    if (!isRecord(report) || typeof report.id !== 'string' || !isState(report.state)
      || ![true, false, null].includes(report.numeric_match as boolean | null)) malformed();
  }
  return value as unknown as Verification;
}

export async function readEvidence(artifactId: string, options?: RequestOptions): Promise<Evidence> {
  if (!artifactId) throw new APIError('Choose an artifact to inspect.', 400, 'missing_artifact');
  const value = await request(`/api/evidence/${encodeURIComponent(artifactId)}`, 'GET', undefined, options);
  if (!isRecord(value) || !isRecord(value.artifact) || value.artifact.id !== artifactId
    || !Array.isArray(value.paths) || !(value.receipt === null || isRecord(value.receipt))) malformed();
  return value as unknown as Evidence;
}

export async function health(options?: RequestOptions): Promise<Health> {
  const value = await request('/health', 'GET', undefined, options);
  if (!isRecord(value) || value.status !== 'ok' || typeof value.backend !== 'string') malformed();
  return value as unknown as Health;
}

export const api = { createSession, readState, applyChange, refresh, reset, verify, readEvidence, health };
