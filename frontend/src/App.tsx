import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, CircleAlert, LoaderCircle, Plus, RefreshCw, ShieldCheck } from 'lucide-react'
import { api } from './lib/api'
import type { SourceChange, Verification, WorkspaceState } from './lib/types'
import ReportPanel from './components/ReportPanel'
import EvidenceGraph from './components/EvidenceGraph'
import ActivityPanel from './components/ActivityPanel'
import SourceDrawer from './components/SourceDrawer'
import EvidenceDrawer from './components/EvidenceDrawer'
import BenchmarkPanel from './components/BenchmarkPanel'

export default function App() {
  const [view, setView] = useState<'workspace' | 'benchmark'>('workspace')
  const [state, setState] = useState<WorkspaceState | null>(null)
  const [pending, setPending] = useState<string | null>('Opening workspace')
  const [error, setError] = useState<string | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [inspectId, setInspectId] = useState<string | null>(null)
  const [verification, setVerification] = useState<Verification | null>(null)
  const closeSource = useCallback(() => setSourceOpen(false), [])
  const closeEvidence = useCallback(() => setInspectId(null), [])

  const load = useCallback(async () => {
    setPending('Opening workspace'); setError(null)
    try { setState(await api.createSession()); setUncertain(false) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'The workspace could not start.'); setUncertain(true) }
    finally { setPending(null) }
  }, [])
  useEffect(() => { void load() }, [load])

  async function mutate(label: string, operation: () => Promise<WorkspaceState>, rethrow = false) {
    setPending(label); setError(null); setVerification(null)
    try { setState(await operation()); setUncertain(false) }
    catch (cause) {
      const message = cause instanceof Error ? cause.message : 'The request did not complete.'
      // A lost mutation response may hide a completed server change. Do not
      // keep presenting the previous snapshot as current until reconciled.
      try { setState(await api.readState()); setUncertain(false) }
      catch { setUncertain(true) }
      setError(message)
      if (rethrow) throw cause
    } finally { setPending(null) }
  }
  async function verify() {
    setPending('Checking fresh recomputation'); setError(null)
    try { setVerification(await api.verify()) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Verification did not complete.') }
    finally { setPending(null) }
  }
  const hasAffected = state?.reports.some(report => report.state !== 'current') ?? false
  const busy = pending !== null
  return <>
    <header className="app-header"><a className="wordmark" href="#workspace" onClick={() => setView('workspace')}>ProofFlow</a><span className="nav-divider" /><nav aria-label="Main navigation"><button className={view === 'workspace' ? 'active' : ''} onClick={() => setView('workspace')} aria-current={view === 'workspace' ? 'page' : undefined}>Workspace</button><button className={view === 'benchmark' ? 'active' : ''} onClick={() => setView('benchmark')} aria-current={view === 'benchmark' ? 'page' : undefined}>Benchmark</button></nav><div className="header-actions"><a className="github-link" href="https://github.com/saivedant169/proofflow" target="_blank" rel="noreferrer" aria-label="Open GitHub repository"><svg width="21" height="21" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .75a11.25 11.25 0 0 0-3.56 21.92c.56.1.77-.24.77-.54v-2.1c-3.13.68-3.79-1.33-3.79-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.03-.71.08-.7.08-.7 1.14.08 1.74 1.17 1.74 1.17 1.01 1.73 2.65 1.23 3.3.94.1-.73.4-1.23.72-1.51-2.5-.29-5.13-1.25-5.13-5.57 0-1.23.44-2.23 1.16-3.02-.12-.29-.5-1.43.11-2.98 0 0 .95-.3 3.1 1.16a10.8 10.8 0 0 1 5.63 0c2.15-1.46 3.1-1.16 3.1-1.16.61 1.55.23 2.69.11 2.98.72.79 1.16 1.79 1.16 3.02 0 4.33-2.63 5.28-5.14 5.56.4.35.76 1.04.76 2.1v3.09c0 .3.2.65.77.54A11.25 11.25 0 0 0 12 .75Z" /></svg><span>GitHub</span></a><span className="nav-divider" /><button className="button button-primary new-workspace" aria-label="New workspace" disabled={busy} onClick={() => { setView('workspace'); void mutate('Creating new workspace', () => state ? api.reset() : api.createSession()) }}><Plus size={16} /><span>New workspace</span></button></div></header>
    {view === 'benchmark' ? <BenchmarkPanel /> : <main className="workspace-page">
      <section className="intro"><div><h1>A change should travel.</h1><p>Trace a correction through the work that depends on it.<br />Refresh what changed. Keep what did not.</p></div><div className="intro-actions"><button className="button button-secondary" onClick={() => setSourceOpen(true)} disabled={busy || !state || uncertain}>Change a source</button><button className="button button-primary" onClick={() => void mutate('Refreshing affected work', () => api.refresh())} disabled={busy || !state || uncertain || !hasAffected}>{pending === 'Refreshing affected work' ? <LoaderCircle size={17} className="spin" /> : <RefreshCw size={16} />}Refresh affected</button></div></section>
      {error && <div className="error-banner" role="alert"><CircleAlert size={18} /><span>{error}</span><button className="text-button" disabled={busy} onClick={() => void load()}>Reload state</button></div>}
      <div aria-live="polite" className="sr-only">{pending ?? (state ? 'Workspace ready' : 'Workspace unavailable')}</div>
      {state && !uncertain ? <>
        {state.impact.change && hasAffected && <div className="impact-banner"><CircleAlert size={17} /><span><strong>{state.impact.change.label}</strong> · {state.impact.affected_artifacts.length} saved artifacts require revalidation.</span></div>}
        {state.last_refresh && !hasAffected && <div className="refresh-banner"><CheckCircle2 size={17} /><span><strong>{state.last_refresh.executed_count} tool calls.</strong> {state.last_refresh.unchanged_support ? 'The independent support result stayed unchanged.' : 'Affected results were re-evaluated.'} {state.last_refresh.numeric_parity === true && 'Fresh recomputation matches.'}</span><button className="text-button" disabled={busy} onClick={() => void verify()}><ShieldCheck size={14} />Check values</button></div>}
        {verification && <div className={`verification-banner ${verification.passed ? 'verified' : 'not-verified'}`} role="status"><ShieldCheck size={18} /><span>{verification.passed ? 'Verified: both report values match fresh recomputation and their evidence is current.' : 'Verification is incomplete. A report is stale, unavailable, or differs from fresh recomputation.'}</span></div>}
        <div className="workspace-grid"><ReportPanel state={state} onInspect={setInspectId} /><EvidenceGraph state={state} onInspect={setInspectId} /></div>
        <ActivityPanel state={state} onInspect={setInspectId} />
      </> : <section className="workspace-loading panel">{busy ? <><LoaderCircle size={28} className="spin" /><h2>Opening your workspace…</h2><p>Checking your reports and their execution evidence in HydraDB.</p></> : <><CircleAlert size={28} /><h2>Current evidence is unavailable.</h2><p>Reconnect to the backend to load this workspace. No cached numbers are being presented as current.</p><button className="button button-secondary" onClick={() => void load()}>Try again</button></>}</section>}
      <footer className="workspace-footer"><span>Authored demo data. Real calculations and HydraDB lineage.</span><button className="text-link" onClick={() => setView('benchmark')}>Inspect the benchmark<ArrowRight size={17} /></button></footer>
    </main>}
    {sourceOpen && state && <SourceDrawer state={state} onClose={closeSource} onApply={(change: SourceChange) => mutate('Applying source correction', () => api.applyChange(change), true)} busy={busy} />}
    {inspectId && <EvidenceDrawer artifactId={inspectId} onClose={closeEvidence} />}
  </>
}
