import { SectionHead, Source } from '../../components/ui'
import Pipeline from './Pipeline'
import { RETAINED_FAILURES, VERIFIED } from './data'
import './styles.css'

export default function Evaluation() {
  return (
    <section id="evaluation" className="section evaluation-section" aria-labelledby="evaluation-title">
      <div className="wrap">
        <SectionHead
          id="evaluation-title"
          title="A method you can check for yourself"
          lede="Protocols are committed before scored runs, held-out cases run once, failures stay on record, and the saved arithmetic can be verified offline."
        />

        <Pipeline />

        <div className="eval-lower">
          <div className="eval-verified">
            <h3 className="eval-sub">Verified in the running product</h3>
            <ul className="eval-facts">
              {VERIFIED.map(f => (
                <li key={f.label}>
                  <p className={`eval-fact-figure figure${f.figure.length > 6 ? ' is-long' : ''}`}>{f.figure}</p>
                  <div className="eval-fact-text">
                    <p className="eval-fact-label">{f.label}</p>
                    <p className="eval-fact-detail">{f.detail}</p>
                    <p className="eval-sources">
                      {f.sources.map(s => <Source key={s} path={s} />)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="eval-failures">
            <h3 className="eval-sub">Failures kept on record</h3>
            <p className="eval-failures-lede">Each one stays in the published evidence instead of being quietly rerun.</p>
            <ul className="eval-failure-list">
              {RETAINED_FAILURES.map(f => (
                <li key={f.what}>
                  <p className="eval-failure-what">{f.what}</p>
                  <p className="eval-failure-kept">{f.kept}</p>
                  <Source path={f.source} />
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}
