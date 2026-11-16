import { links, project, repoFile } from '../../content/facts'

const FOOTER_LINKS = [
  { label: 'Live app', href: links.liveApp },
  { label: 'Walkthrough', href: links.walkthrough },
  { label: 'Evidence', href: links.publicEvidence },
  { label: 'Connector', href: links.connector },
  { label: 'Repository', href: links.repo },
] as const

export default function Footer() {
  return (
    <footer className="try-footer" aria-labelledby="try-footer-name">
      <div className="wrap try-footer-inner">
        <div className="try-footer-brand">
          <p className="try-footer-name" id="try-footer-name">{project.name}</p>
          <p className="try-footer-promise">{project.promise}</p>
        </div>

        <nav className="try-footer-nav" aria-label="Footer">
          <ul>
            {FOOTER_LINKS.map(l => (
              <li key={l.label}>
                <a href={l.href} target="_blank" rel="noreferrer">
                  {l.label}<span className="sr-only"> (opens in a new tab)</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="try-footer-fine">
          <p>
            Built for the {project.track}.
          </p>
          <p>
            Application code <a href={repoFile('LICENSE')} target="_blank" rel="noreferrer">MIT-licensed</a>.
            {' '}HydraDB is a separate upstream dependency under its own license.
          </p>
          <p>
            Retail data: Chen, D. (2015). <cite>Online Retail</cite> [Dataset]. UCI Machine Learning Repository.{' '}
            <a href="https://doi.org/10.24432/C5BW33" target="_blank" rel="noreferrer">doi.org/10.24432/C5BW33</a>,
            licensed{' '}
            <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>.
            ProofFlow uses a modified, bounded positive-sales sample; the project is not endorsed by the creator or UCI.{' '}
            <a href={repoFile('fixtures/retail_v2/DATASET_NOTICE.md')} target="_blank" rel="noreferrer">Dataset notice</a>.
          </p>
        </div>
      </div>
    </footer>
  )
}
