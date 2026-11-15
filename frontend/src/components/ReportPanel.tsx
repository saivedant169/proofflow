import { Fragment } from 'react'
import { ArrowUpRight, Check, CircleAlert, Layers } from 'lucide-react'
import type { Claim, WorkspaceState } from '../lib/types'
import { formatValue } from '../lib/format'
import Status from './Status'

function Metric({ claim, main = false, blocked = false, onInspect }: { claim?: Claim; main?: boolean; blocked?: boolean; onInspect: (id: string) => void }) {
  if (!claim) return <div className="metric-missing">This claim is unavailable.</div>
  const current = !blocked && claim.state === 'current' && claim.value !== null
  const value = current ? formatValue(claim.value, claim.unit) : !blocked && claim.state === 'stale' ? 'Awaiting refresh' : 'Unavailable'
  const longAmount = current && claim.unit === 'USD cents' && value.length > 18
  return <button className={`metric ${main ? 'metric-main' : ''} ${current ? '' : 'metric-withheld'}`} onClick={() => onInspect(claim.artifact_id)} aria-label={`Inspect evidence for ${claim.label}`}>
    {!main && <span className="metric-label">{claim.label}<ArrowUpRight size={14} /></span>}
    <strong className={longAmount ? 'metric-long-amount' : undefined}>{longAmount ? value.split(',').map((group, index) => (
      <Fragment key={index}>{index > 0 ? <>,<wbr /></> : null}{group}</Fragment>
    )) : value}</strong>
    {main && <span className="metric-label">{claim.label}{claim.unit === 'USD cents' ? ' · USD' : ''} <ArrowUpRight size={14} /></span>}
    {!current && <span className="historical">Previously {formatValue(claim.saved_value, claim.unit)}</span>}
    {current && !main && <span className="metric-current"><Check size={12} /> Current</span>}
  </button>
}

export default function ReportPanel({ state, onInspect }: { state: WorkspaceState; onInspect: (id: string) => void }) {
  const company = state.reports.find(report => report.key === 'company') ?? state.reports[0]
  const allClaims = state.reports.flatMap(report => report.claims)
  const revenue = allClaims.find(claim => claim.key === 'company_revenue')
  const regional = allClaims.find(claim => claim.key === 'eu_revenue' || claim.key === 'regional_revenue')
  const support = allClaims.find(claim => claim.key === 'eu_support')
  const withheld = allClaims.some(claim => claim.state !== 'current')
  const imported = state.mode === 'guided_csv_import'
  const blocked = imported && state.incomplete_update
  const importedSupport = imported ? state.graph.nodes.find(node => node.current_head && node.logical_id === 'import:metric:support') : undefined
  return <section className="report-panel panel" aria-labelledby="report-title">
    <div className="report-top"><h2 id="report-title">Saved reports</h2><Status state={blocked ? 'unknown' : company?.state ?? 'unknown'} compact /></div>
    {withheld && <p className="withheld-notice"><CircleAlert size={17} aria-hidden="true" /><span>Affected figures are withheld until refreshed. Previous values are historical.</span></p>}
    <Metric claim={revenue} main blocked={blocked} onInspect={onInspect} />
    <div className="secondary-metrics"><Metric claim={regional} blocked={blocked} onInspect={onInspect} />{support && <Metric claim={support} blocked={blocked} onInspect={onInspect} />}</div>
    {importedSupport && <div className="import-report-note">
      <button className="text-link" onClick={() => onInspect(importedSupport.id)}>View separate support calculation<ArrowUpRight size={14} aria-hidden="true" /></button>
      <Status state={blocked ? 'unknown' : importedSupport.state} compact />
    </div>}
    <div className="report-provenance"><div className="provenance-title"><Layers size={16} aria-hidden="true" /><strong>Inspect report evidence</strong></div>
      {state.reports.map(report => <button key={report.id} onClick={() => onInspect(report.id)}><span>{report.title}</span><ArrowUpRight size={14} aria-hidden="true" /></button>)}
    </div>
  </section>
}
