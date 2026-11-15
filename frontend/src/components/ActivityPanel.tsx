import { CheckCircle2, ChevronDown, Clock3 } from 'lucide-react'
import { useState } from 'react'
import type { WorkspaceState } from '../lib/types'
import { toolLabels } from '../lib/format'

function runLabel(runId: string) {
  if (runId === 'run-A') return 'Run 1 · Company report'
  if (runId === 'run-B') return 'Run 2 · Reused results'
  if (runId.startsWith('refresh-')) return 'Selective refresh'
  return runId
}

export default function ActivityPanel({ state, onInspect }: { state: WorkspaceState; onInspect: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const recent = [...state.executions].reverse()
  const visible = expanded ? recent : recent.slice(0, 3)
  return <section className="activity-panel panel" aria-labelledby="activity-title"><div className="section-heading"><h2 id="activity-title">Recent activity</h2><button className="text-button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show less' : `All ${recent.length} executions`}<ChevronDown size={14} className={expanded ? 'rotated' : ''} /></button></div>
    <div className="activity-list">{visible.map(execution => <button key={execution.id} className="activity-row" onClick={() => execution.output_id && onInspect(execution.output_id)} disabled={!execution.output_id}>
      {execution.status === 'success' ? <CheckCircle2 className="success-icon" size={20} /> : <Clock3 size={20} />}
      <strong>{execution.tool === 'compose_report' && typeof execution.params?.title === 'string' ? `${execution.params.title} composed` : toolLabels[execution.tool] ?? execution.tool}</strong><span className="activity-run" title={execution.run_id}>{runLabel(execution.run_id)}</span><span className="activity-time">{Number.isFinite(execution.elapsed_ms) ? execution.elapsed_ms < 0.1 ? '<0.1 ms' : `${execution.elapsed_ms.toFixed(1)} ms` : 'Recorded'}</span>
    </button>)}</div>
  </section>
}
