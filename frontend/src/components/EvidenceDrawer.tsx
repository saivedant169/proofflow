import { useEffect, useState } from 'react'
import { ArrowDown, ExternalLink, LoaderCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { Evidence } from '../lib/types'
import Drawer from './Drawer'
import Status from './Status'

export default function EvidenceDrawer({ artifactId, onClose, imported = false, incompleteImport = false }: { artifactId: string; onClose: () => void; imported?: boolean; incompleteImport?: boolean }) {
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const abort = new AbortController()
    setEvidence(null); setError(null)
    const read = imported ? api.readImportEvidence : api.readEvidence
    read(artifactId, { signal: abort.signal }).then(setEvidence).catch(cause => { if (!abort.signal.aborted) setError(cause.message) })
    return () => abort.abort()
  }, [artifactId, imported])
  const title = evidence ? String(evidence.artifact.metadata.title ?? evidence.artifact.logical_id) : 'Inspect evidence'
  return <Drawer title="Inspect evidence" subtitle="The inputs behind the result." onClose={onClose} wide>
    {incompleteImport && <div className="inline-error" role="status">CSV publication is incomplete. This is prior artifact evidence, not a repaired report. Artifact currentness below describes its saved dependencies; the workspace is blocked until the full corrected CSV is published.</div>}
    {!evidence && !error && <div className="drawer-loading"><LoaderCircle className="spin" />Reading persisted evidence…</div>}
    {error && <div className="inline-error" role="alert">{error}</div>}
    {evidence && <div className="evidence-details"><div className="evidence-name"><h3>{title}</h3><Status state={evidence.artifact.state} /></div>
      <dl className="evidence-facts"><div><dt>Immutable artifact</dt><dd className="mono">{evidence.artifact.id}</dd></div><div><dt>Content fingerprint</dt><dd className="mono">{evidence.artifact.content_hash}</dd></div>{evidence.receipt && <div><dt>Producing tool</dt><dd>{String(evidence.receipt.tool ?? evidence.artifact.metadata.tool ?? 'Recorded execution')}</dd></div>}</dl>
      <section className="evidence-section"><h3>Why this is affected</h3>{evidence.paths.length ? evidence.paths.map((path, index) => <ol className="evidence-path" key={`${path.source_id}-${index}`}>{path.nodes.map((node, step) => <li key={`${node.id}-${step}`}><span>{node.label}</span><small>{node.kind}</small>{step < path.nodes.length - 1 && <ArrowDown size={14} />}</li>)}</ol>) : <p className="muted">No native path from the latest changed source to this artifact. It may be unchanged, or already refreshed from a newer version.</p>}<p className="inspector-note">Paths are queried from HydraDB. Execution nodes retain the exact consumed and produced versions.</p></section>
      <details className="evidence-raw"><summary>Execution receipt <ExternalLink size={13} /></summary><pre>{evidence.receipt ? JSON.stringify(evidence.receipt, null, 2) : 'Source snapshot — no producing tool receipt.'}</pre></details>
      <details className="evidence-raw"><summary>Historical stored value</summary><p className="inspector-note">This is the immutable saved value. Currentness is shown separately above.{evidence.display_saved_value !== undefined ? ' Large USD cent amounts appear as decimal strings to preserve every digit.' : null}</p><pre>{JSON.stringify(evidence.display_saved_value ?? evidence.artifact.saved_value, null, 2)}</pre></details>
    </div>}
  </Drawer>
}
