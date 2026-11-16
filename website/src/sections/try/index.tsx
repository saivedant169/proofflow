import { ChevronRight, FileArchive, Lock, Play, Plug } from 'lucide-react'
import { ButtonLink, SectionHead, Source } from '../../components/ui'
import { links } from '../../content/facts'
import CopyCode from './CopyCode'
import Footer from './Footer'
import './styles.css'

const GUIDED_STEPS = ['Change a source', 'Exchange rate', 'Apply correction', 'Refresh affected']

const RUN_LINES = [
  'python3 scripts/init_local.py',
  'docker compose -f docker-compose.yml -f compose.app.yml up -d --build',
]

const TEST_LINES = [
  'uv sync --frozen --extra test --extra benchmark',
  'uv run pytest -q',
]

const LOCAL_URL = 'http://127.0.0.1:18080'

export default function TryIt() {
  return (
    <>
      <section id="try" className="section try-section" aria-labelledby="try-title">
        <div className="wrap">
          <SectionHead
            id="try-title"
            title="Try it now"
            lede="Open the live app, watch the two-minute walkthrough, or run the same stack on your own machine."
          />

          {/* Primary path: the hosted app */}
          <div className="try-live">
            <div className="try-live-text">
              <h3 className="try-h">Use the live app</h3>
              <p className="try-p">
                Follow the guided sample to correct an exchange rate, see which figures are withheld, then refresh only
                the affected work.
              </p>
              <ol className="try-guided" aria-label="Guided sample, the controls to choose in order">
                {GUIDED_STEPS.map((s, i) => (
                  <li key={s}>
                    <span className="try-ctl">{s}</span>
                    {i < GUIDED_STEPS.length - 1 && <ChevronRight className="try-ctl-sep" size={16} strokeWidth={2} aria-hidden />}
                  </li>
                ))}
              </ol>
              <p className="try-p try-p-soft">
                Or choose <strong>Use your data</strong> and upload an orders CSV. It is sent to the ProofFlow server, not
                to a model.
              </p>
              <div className="try-actions">
                <ButtonLink href={links.liveApp} external>Open the live app</ButtonLink>
              </div>
              <p className="try-src"><Source path="README.md" /></p>
            </div>

            <figure className="try-shot">
              <img
                src={import.meta.env.BASE_URL + "shots/workspace-final.jpg"}
                width={1536}
                height={1031}
                loading="lazy"
                decoding="async"
                alt="The ProofFlow workspace before a correction: company revenue $5,565.00, EU revenue $2,090.00 and 2 EU support tickets, all current, beside a graph that connects FX rates, orders, refunds and tickets through calculations to the two reports."
              />
              <figcaption>The guided sample in the live app, before a correction.</figcaption>
            </figure>
          </div>

          {/* Walkthrough */}
          <div className="try-watch">
            <div className="try-watch-text">
              <h3 className="try-h">Watch the walkthrough</h3>
              <p className="try-p">
                Two minutes: CSV preview and report creation, a guided correction, the audited 48-invocation model
                comparison and saved MCP-client evidence.
              </p>
              <div className="try-actions">
                <ButtonLink variant="quiet" href={links.walkthrough} external icon={<Play size={16} strokeWidth={2} aria-hidden />}>
                  Open the video file
                </ButtonLink>
              </div>
              <p className="try-src"><Source path="README.md" /></p>
            </div>
            <figure className="try-video">
              <div className="try-video-frame">
                <video
                  controls
                  preload="none"
                  playsInline
                  poster={import.meta.env.BASE_URL + "shots/walkthrough-poster.jpg"}
                  width={1920}
                  height={1080}
                  aria-label="ProofFlow two-minute walkthrough"
                  src={links.walkthrough}
                >
                  Your browser cannot play this video. <a href={links.walkthrough}>Download the walkthrough</a>.
                </video>
              </div>
            </figure>
          </div>

          {/* Local run and agent connection */}
          <div className="try-build">
            <div className="try-local">
              <h3 className="try-h">Run it locally</h3>
              <p className="try-p">Needs Docker and Python 3. The first command creates local credentials; the second starts HydraDB and the app.</p>
              <CopyCode label="Start the stack" lines={RUN_LINES} />
              <p className="try-p try-open-local">
                Then open <a href={LOCAL_URL} className="try-mono">{LOCAL_URL}</a>
              </p>
              <CopyCode label="Run the tests (no model credentials needed)" lines={TEST_LINES} />
              <p className="try-src"><Source path="README.md" /></p>
            </div>

            <div className="try-agent">
              <Plug className="try-icon" size={22} strokeWidth={1.8} aria-hidden />
              <h3 className="try-h">Connect your agent</h3>
              <p className="try-p">
                A local MCP host can create, inspect, correct, refresh and export the same two CSV revenue reports as
                the browser. No repository checkout, ProofFlow account or HydraDB key is required.
              </p>
              <p className="try-p try-p-soft">Needs <code>uv</code> and Python 3.11 or newer. Verify the script against its published checksum first.</p>
              <div className="try-actions">
                <ButtonLink href={links.connector} external variant="secondary">Set up the connector</ButtonLink>
                <ButtonLink href={links.connectorScript} external variant="quiet">Get the Python script</ButtonLink>
              </div>
              <p className="try-src"><Source path="README.md" /></p>
            </div>
          </div>

          {/* Evidence and source */}
          <div className="try-more">
            <div className="try-more-item">
              <FileArchive className="try-icon" size={22} strokeWidth={1.8} aria-hidden />
              <div>
                <h3 className="try-h try-h-sm">Verify the evidence</h3>
                <p className="try-p">
                  The ZIP includes the saved model study and a Python standard-library verifier. It checks the arithmetic,
                  receipt provenance, provider counters and historical failures offline.
                </p>
                <div className="try-actions">
                  <ButtonLink href={links.evidenceZip} variant="secondary">Download the evidence ZIP</ButtonLink>
                  <ButtonLink href={links.publicEvidence} external variant="quiet">Open the evidence page</ButtonLink>
                </div>
                <p className="try-src"><Source path="docs/PUBLIC_EVIDENCE.md" /></p>
              </div>
            </div>

            <div className="try-more-item">
              <Lock className="try-icon" size={22} strokeWidth={1.8} aria-hidden />
              <div>
                <h3 className="try-h try-h-sm">Read the source</h3>
                <p className="try-p">
                  The repository is private and opens for judges with approved access. The live app and the evidence
                  verifier work without it.
                </p>
                <div className="try-actions">
                  <ButtonLink href={links.repo} external variant="secondary">Open the repository</ButtonLink>
                </div>
                <p className="try-src"><Source path="README.md" /></p>
              </div>
            </div>
          </div>
        </div>
      </section>
      <Footer />
    </>
  )
}
