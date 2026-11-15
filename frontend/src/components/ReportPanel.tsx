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
  const blocked = state.mode === 'guided_csv_import' && state.incomplete_update
  return <section className="report-panel panel" aria-labelledby="report-title">
    <div className="report-top"><span>{company?.title ?? 'Company weekly report'}</span><Status state={blocked ? 'unknown' : company?.state ?? 'unknown'} compact /></div>
    <h2 id="report-title">{state.mode === 'guided_csv_import' ? 'Your numbers, with their working attached.' : 'The week, with its working attached.'}</h2>
    {withheld && <p className="withheld-notice"><CircleAlert size={17} /><span>A source changed. Affected claims are withheld until recomputed.</span></p>}
    <Metric claim={revenue} main blocked={blocked} onInspect={onInspect} />
    <div className="secondary-metrics"><Metric claim={regional} blocked={blocked} onInspect={onInspect} />{support && <Metric claim={support} blocked={blocked} onInspect={onInspect} />}</div>
    {state.mode === 'guided_csv_import' && <p className="import-report-note">Revenue-only reports. Supplied ticket counts remain a separate, inspectable calculation.</p>}
    <div className="report-provenance"><div className="provenance-title"><Layers size={16} /><strong>{state.mode === 'guided_csv_import' ? 'Reports with saved evidence' : 'Composed from two runs'}</strong></div>
      {state.reports.map((report, index) => <button key={report.id} onClick={() => onInspect(report.id)}><span>Run {index + 1} · {report.title}</span><ArrowUpRight size={14} /></button>)}
    </div>
  </section>
}
