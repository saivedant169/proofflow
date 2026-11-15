import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, CircleAlert, Database, Download, FileUp, LoaderCircle, Plus, RefreshCw, ShieldCheck } from 'lucide-react'
import { api } from './lib/api'
import { parseUSDCents } from './lib/format'
import type { ImportExport, ImportExportRequest, ImportedWorkspaceState, ImportRequest, SourceChange, Verification, WorkspaceState } from './lib/types'
import ReportPanel from './components/ReportPanel'
import EvidenceGraph from './components/EvidenceGraph'
import ActivityPanel from './components/ActivityPanel'
import SourceDrawer from './components/SourceDrawer'
import EvidenceDrawer from './components/EvidenceDrawer'
import BenchmarkPanel from './components/BenchmarkPanel'
import ImportDrawer from './components/ImportDrawer'
import './import-workspace.css'

type WorkspaceKind = 'demo' | 'import'
const exportTimeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'long', timeZone: 'UTC' })

function preferredWorkspace(): WorkspaceKind {
  try { return sessionStorage.getItem('proofflow-workspace-kind') === 'import' ? 'import' : 'demo' }
  catch { return 'demo' }
}

function currentReportId(state: ImportedWorkspaceState, key: string, claimKey: string) {
  const report = state.reports.find(item => item.key === key)
  if (!report?.id || report.state !== 'current' || report.claims.length !== 1) return null
  const [claim] = report.claims
  return claim.key === claimKey && claim.state === 'current' && claim.unit === 'USD cents'
    && parseUSDCents(claim.value) !== null ? report.id : null
}

function exportRequest(state: ImportedWorkspaceState | null): ImportExportRequest | null {
  if (!state?.generation || state.incomplete_update || state.reports.length !== 2) return null
  const company = currentReportId(state, 'company', 'company_revenue')
  const region = currentReportId(state, 'region', 'regional_revenue')
  return company && region && company !== region ? { generation: state.generation, report_ids: { company, region } } : null
}

function downloadTextFile(file: ImportExport) {
  const url = URL.createObjectURL(new Blob([file.content], { type: file.media_type }))
  const link = document.createElement('a')
  link.href = url
  link.download = file.filename
  link.hidden = true
  try {
    document.body.append(link)
    link.click()
  } finally {
    link.remove()
    // Let the browser acquire the blob before releasing its object URL.
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}

export default function App() {
  const [view, setView] = useState<'workspace' | 'benchmark'>('workspace')
  const [state, setState] = useState<WorkspaceState | null>(null)
  const [pending, setPending] = useState<string | null>('Opening workspace')
  const [error, setError] = useState<string | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [importOpen, setImportOpen] = useState<'create' | 'update' | null>(null)
  const [kind, setKind] = useState<WorkspaceKind>(preferredWorkspace)
  const [hasImported, setHasImported] = useState(preferredWorkspace() === 'import')
  const [importDraft, setImportDraft] = useState<{ generation: string; request: ImportRequest } | null>(null)
  const [inspectId, setInspectId] = useState<string | null>(null)
  const [verification, setVerification] = useState<Verification | null>(null)
  const [exportCheckedAt, setExportCheckedAt] = useState<string | null>(null)
  const closeSource = useCallback(() => setSourceOpen(false), [])
  const closeImport = useCallback(() => setImportOpen(null), [])
  const closeEvidence = useCallback(() => setInspectId(null), [])

  const acceptState = useCallback((next: WorkspaceState) => {
    const nextKind = next.mode === 'guided_csv_import' ? 'import' : 'demo'
    setState(next); setKind(nextKind); setUncertain(false)
    if (nextKind === 'import') setHasImported(true)
    try { sessionStorage.setItem('proofflow-workspace-kind', nextKind) } catch { /* Preference persistence is optional. */ }
  }, [])
  const load = useCallback(async (target: WorkspaceKind = preferredWorkspace()) => {
    setPending('Opening workspace'); setError(null); setKind(target); setUncertain(true)
    setVerification(null); setInspectId(null); setExportCheckedAt(null)
    try { acceptState(await (target === 'import' ? api.readImportState() : api.createSession())) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'The workspace could not start.'); setUncertain(true) }
    finally { setPending(null) }
  }, [acceptState])
  useEffect(() => { void load() }, [load])

  async function mutate(label: string, operation: () => Promise<WorkspaceState>, rethrow = false, target: WorkspaceKind = kind) {
    setPending(label); setError(null); setVerification(null); setKind(target); setExportCheckedAt(null)
    try { const next = await operation(); acceptState(next); return next }
    catch (cause) {
      const message = cause instanceof Error ? cause.message : 'The request did not complete.'
      // A lost mutation response may hide a completed server change. Do not
      // keep presenting the previous snapshot as current until reconciled.
      try { acceptState(await (target === 'import' ? api.readImportState() : api.readState())) }
      catch { setUncertain(true) }
      setError(message)
      if (rethrow) throw cause
    } finally { setPending(null) }
  }
  async function verify() {
    setPending('Checking fresh recomputation'); setError(null); setExportCheckedAt(null)
    try {
      if (kind === 'import') {
        const result = await api.verifyImport()
        setVerification(result)
        // The verification endpoint reports real computation accounting.
        setState(previous => previous?.mode === 'guided_csv_import' ? { ...previous, last_operation: result.accounting } : previous)
      } else setVerification(await api.verify())
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Verification did not complete.') }
    finally { setPending(null) }
  }
  async function importCSV(request: ImportRequest) {
    const update = importOpen === 'update'
    const next = await mutate(update ? 'Publishing CSV correction' : 'Creating CSV reports', () => update ? api.updateImport(request) : api.createImport(request), true, 'import')
    if (next) setImportDraft({ generation: next.generation, request })
    setView('workspace')
  }
  const imported = state?.mode === 'guided_csv_import' ? state : null
  const hasAffected = (state?.reports.some(report => report.state !== 'current') || state?.graph.nodes.some(node => node.current_head && node.kind === 'artifact' && node.state !== 'current')) ?? false
  const busy = pending !== null
  const downloadRequest = exportRequest(imported)
  const canDownload = !busy && !uncertain && downloadRequest !== null

  async function downloadCurrentReports() {
    if (!canDownload || !downloadRequest) return
    setPending('Checking reports for download'); setError(null); setExportCheckedAt(null)
    try {
      const file = await api.exportImport(downloadRequest)
      downloadTextFile(file)
      setExportCheckedAt(file.checked_at)
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'The download request did not complete.'
      setUncertain(true); setVerification(null); setInspectId(null)
      try { acceptState(await api.readImportState()) }
      catch { /* Keep unconfirmed reports withheld until the workspace can be read. */ }
      setError(`No report file was downloaded. ${message}`)
    } finally { setPending(null) }
  }

  return <>
    <header className="app-header"><a className="wordmark" href="#workspace" onClick={() => setView('workspace')}>ProofFlow</a><span className="nav-divider" /><nav aria-label="Main navigation"><button className={view === 'workspace' ? 'active' : ''} onClick={() => setView('workspace')} aria-current={view === 'workspace' ? 'page' : undefined}>Workspace</button><button className={view === 'benchmark' ? 'active' : ''} onClick={() => setView('benchmark')} aria-current={view === 'benchmark' ? 'page' : undefined}>Benchmark</button></nav><div className="header-actions"><a className="github-link" href="https://github.com/saivedant169/proofflow" target="_blank" rel="noreferrer" aria-label="Open GitHub repository"><svg width="21" height="21" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .75a11.25 11.25 0 0 0-3.56 21.92c.56.1.77-.24.77-.54v-2.1c-3.13.68-3.79-1.33-3.79-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.03-.71.08-.7.08-.7 1.14.08 1.74 1.17 1.74 1.17 1.01 1.73 2.65 1.23 3.3.94.1-.73.4-1.23.72-1.51-2.5-.29-5.13-1.25-5.13-5.57 0-1.23.44-2.23 1.16-3.02-.12-.29-.5-1.43.11-2.98 0 0 .95-.3 3.1 1.16a10.8 10.8 0 0 1 5.63 0c2.15-1.46 3.1-1.16 3.1-1.16.61 1.55.23 2.69.11 2.98.72.79 1.16 1.79 1.16 3.02 0 4.33-2.63 5.28-5.14 5.56.4.35.76 1.04.76 2.1v3.09c0 .3.2.65.77.54A11.25 11.25 0 0 0 12 .75Z" /></svg><span>GitHub</span></a><span className="nav-divider" /><button className="button button-primary new-workspace" aria-label="New workspace" disabled={busy} onClick={() => { setView('workspace'); if (kind === 'import') setImportOpen('create'); else void mutate('Creating new workspace', () => state ? api.reset() : api.createSession(), false, 'demo') }}><Plus size={16} /><span>New workspace</span></button></div></header>
    {view === 'benchmark' ? <BenchmarkPanel /> : <main className="workspace-page">
      <section className="intro"><div><h1>A change should travel.</h1><p>Trace a correction through the work that depends on it.<br />Refresh what changed. Keep what did not.</p></div><div className="intro-actions"><button className="button button-secondary" onClick={() => imported ? setImportOpen('update') : setSourceOpen(true)} disabled={busy || !state || uncertain}>{imported ? 'Update CSV' : 'Change a source'}</button><button className="button button-primary" onClick={() => void mutate('Refreshing affected work', () => imported ? api.refreshImport() : api.refresh())} disabled={busy || !state || uncertain || !hasAffected || imported?.incomplete_update}>{pending === 'Refreshing affected work' ? <LoaderCircle size={17} className="spin" /> : <RefreshCw size={16} />}Refresh affected</button></div></section>
      <div className="dataset-bar"><div><Database size={17} /><span><strong>{imported ? 'Your CSV workspace' : 'Guided demo'}</strong><small>{imported ? `${imported.dataset.row_count.toLocaleString()} orders · ${imported.dataset.selected_region} regional report · supplied CSV and rates` : 'Authored commerce data · real calculations'}</small></span></div><div className="dataset-actions">{kind === 'import' ? <button className="text-button" disabled={busy} onClick={() => void load('demo')}>Guided demo</button> : hasImported && <button className="text-button" disabled={busy} onClick={() => void load('import')}>Open your CSV</button>}<button className="text-link" disabled={busy} onClick={() => setImportOpen('create')}><FileUp size={15} />{imported ? 'Import another CSV' : 'Use your data'}<ArrowRight size={15} /></button></div></div>
      {kind === 'import' && <div className="report-export">
        <button className="button button-secondary" disabled={!canDownload} onClick={() => void downloadCurrentReports()}>
          {pending === 'Checking reports for download' ? <LoaderCircle size={16} className="spin" aria-hidden="true" /> : <Download size={16} aria-hidden="true" />}
          Download current reports
        </button>
        {exportCheckedAt && <p role="status">Snapshot checked at <time dateTime={exportCheckedAt}>{exportTimeFormat.format(new Date(exportCheckedAt))}</time>. This file does not update automatically.</p>}
      </div>}
      {error && <div className="error-banner" role="alert"><CircleAlert size={18} /><span>{error}</span><button className="text-button" disabled={busy} onClick={() => void load(kind)}>Reload state</button></div>}
      <div aria-live="polite" className="sr-only">{pending ?? (state ? 'Workspace ready' : 'Workspace unavailable')}</div>
      {state && !uncertain ? <>
        {imported?.incomplete_update && <div className="error-banner" role="alert"><CircleAlert size={18} /><span>Source publication is incomplete. Re-upload the complete corrected CSV before refreshing. No report should be treated as current until the update succeeds.</span></div>}
        {imported && <div className="import-accounting"><div><strong>Last completed operation · {({ create: 'CSV reports created', update: 'CSV correction checked', refresh: 'Affected work refreshed', verify: 'Saved values checked' })[imported.last_operation.kind]}</strong>{imported.last_operation.kind === 'update' && <span>{imported.last_operation.noop ? 'Canonical sources unchanged.' : `${imported.last_operation.changed_source_count} source versions changed.`}</span>}</div><p><strong>{imported.last_operation.preflight_calculation_count}</strong> validation calculations <span>+</span> <strong>{imported.last_operation.recorded_tool_call_count}</strong> recorded tool calls <span>+</span> <strong>{imported.last_operation.verification_calculation_count}</strong> check calculations <span>=</span> <strong>{imported.last_operation.total_calculation_count}</strong> in this operation.</p><small>Preview validation is a separate operation. Only recorded tool calls appear in activity below.</small></div>}
        {state.impact.change && hasAffected && <div className="impact-banner"><CircleAlert size={17} /><span><strong>{state.impact.change.label}</strong> · {state.impact.affected_artifacts.length} saved artifacts require revalidation.</span></div>}
        {state.last_refresh && !hasAffected && !imported?.incomplete_update && (!imported || imported.last_operation.kind === 'refresh') && <div className="refresh-banner"><CheckCircle2 size={17} /><span><strong>{state.last_refresh.executed_count} tool calls.</strong> {state.last_refresh.unchanged_support ? 'The independent support result stayed unchanged.' : 'Affected results were re-evaluated.'} {state.last_refresh.numeric_parity === true && 'Fresh recomputation matches.'}</span><button className="text-button" disabled={busy} onClick={() => void verify()}><ShieldCheck size={14} />Check values</button></div>}
        {verification && <div className={`verification-banner ${verification.passed ? 'verified' : 'not-verified'}`} role="status"><ShieldCheck size={18} /><span>{verification.passed ? 'Verified: both report values match fresh recomputation and their evidence is current.' : 'Verification is incomplete. A report is stale, unavailable, or differs from fresh recomputation.'}</span></div>}
        <div className="workspace-grid"><ReportPanel state={state} onInspect={setInspectId} /><EvidenceGraph state={state} onInspect={setInspectId} /></div>
        <ActivityPanel state={state} onInspect={setInspectId} />
      </> : <section className="workspace-loading panel">{busy ? <><LoaderCircle size={28} className="spin" /><h2>Opening your workspace…</h2><p>Checking your reports and their execution evidence in HydraDB.</p></> : <><CircleAlert size={28} /><h2>Current evidence is unavailable.</h2><p>Reconnect to the backend to load this workspace. No cached numbers are being presented as current.</p><button className="button button-secondary" onClick={() => void load(kind)}>Try again</button></>}</section>}
      <footer className="workspace-footer"><span>{imported ? 'Imported CSV. Guided calculations and HydraDB lineage. No live model.' : 'Authored demo data. Real calculations and HydraDB lineage.'}</span><button className="text-link" onClick={() => setView('benchmark')}>Inspect the benchmark<ArrowRight size={17} /></button></footer>
    </main>}
    {sourceOpen && state && <SourceDrawer state={state} onClose={closeSource} onApply={async (change: SourceChange) => { await mutate('Applying source correction', () => api.applyChange(change), true, 'demo') }} busy={busy} />}
    {importOpen && <ImportDrawer existing={importOpen === 'update' ? imported : null} initial={importOpen === 'update' && importDraft && imported && importDraft.generation === imported.generation ? importDraft.request : null} onClose={closeImport} onApply={importCSV} busy={busy} />}
    {inspectId && <EvidenceDrawer artifactId={inspectId} imported={!!imported} incompleteImport={imported?.incomplete_update} onClose={closeEvidence} />}
  </>
}
