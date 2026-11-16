import { StateTag, type ClaimState as TagState } from '../../components/ui'
import type { LastRefresh } from './engine'
import { SOURCE_LABEL, money, type ClaimView, type ReportView } from './model'

const fmt = (claim: ClaimView, value: number) => (claim.unit === 'USD cents' ? money(value) : String(value))

function reportTag(report: ReportView): { state: TagState; text: string } {
  if (report.state === 'blocked') {
    const all = report.claims.every(claim => claim.state === 'blocked')
    return { state: 'blocked', text: all ? 'Blocked' : 'Partly blocked' }
  }
  if (report.state === 'stale' || report.state === 'unknown') return { state: 'stale', text: 'Needs refresh' }
  if (report.badge === 'refreshed') return { state: 'refreshed', text: 'Refreshed' }
  return { state: 'current', text: 'Current' }
}

function Claim({ claim, previous, refresh }: { claim: ClaimView; previous: number | undefined; refresh: LastRefresh | null }) {
  const reused = refresh?.reusedArtifactIds.includes(claim.artifactId)
  const recomputed = refresh?.executedArtifactIds.includes(claim.artifactId)
  const showWas = claim.state === 'current' && previous !== undefined && previous !== claim.value
  return (
    <div className={`demo-claim is-${claim.state}`}>
      <dt className="demo-claim-label">{claim.label}</dt>
      <dd className="demo-claim-body">
        {claim.state === 'current' && claim.value !== null ? (
          <span className="demo-claim-value figure">{fmt(claim, claim.value)}</span>
        ) : (
          <span className="demo-claim-value figure is-withheld">
            <span className="demo-withheld-word">{claim.state === 'blocked' ? 'Blocked' : 'Withheld'}</span>
            <span className="sr-only">. </span>
          </span>
        )}
        <span className="demo-claim-note">
          {claim.state === 'current' && showWas && <>Was {fmt(claim, previous!)}. </>}
          {claim.state === 'current' && reused && 'Same artifact, reused.'}
          {claim.state === 'current' && !reused && recomputed && !showWas && 'Recomputed, same value.'}
          {claim.state === 'stale' && <>Saved value {fmt(claim, claim.savedValue)} is historical, not shown as current.</>}
          {claim.state === 'unknown' && <>Saved value {fmt(claim, claim.savedValue)} cannot be validated.</>}
          {claim.state === 'blocked' && <>Needs {claim.blockedBy.map(name => SOURCE_LABEL[name]).join(' and ')}, which was removed. Refresh cannot recover it.</>}
        </span>
      </dd>
    </div>
  )
}

export default function Reports({ reports, previous, refresh }: {
  reports: ReportView[]
  previous: Record<string, number>
  refresh: LastRefresh | null
}) {
  return (
    <section className="demo-reports" aria-labelledby="demo-reports-title">
      <h3 className="demo-panel-title" id="demo-reports-title">Saved reports</h3>
      <div className="demo-report-pair">
        {reports.map(report => {
          const tag = reportTag(report)
          return (
            <article className="demo-report" key={report.key} aria-labelledby={`demo-report-${report.key}`}>
              <header className="demo-report-head">
                <h4 id={`demo-report-${report.key}`}>{report.title}</h4>
                <StateTag state={tag.state}>{tag.text}</StateTag>
              </header>
              <p className="demo-report-run soft">Saved by <code>{report.runId}</code></p>
              <dl className="demo-claims">
                {report.claims.map(claim => (
                  <Claim key={claim.key} claim={claim} previous={previous[`${report.key}:${claim.key}`]} refresh={refresh} />
                ))}
              </dl>
            </article>
          )
        })}
      </div>
    </section>
  )
}
