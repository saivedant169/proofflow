import { useRef, useState, type KeyboardEvent } from 'react'
import { motion } from 'motion/react'
import { ShieldCheck } from 'lucide-react'
import { ButtonLink, SectionHead, Source } from '../../components/ui'
import { links } from '../../content/facts'
import { fixedBudget, limits, modelStudy, onRecord, retail, verifier } from './data'
import { BarChart, Dumbbell, RetailTable, ShareBars } from './charts'
import './styles.css'

const STUDIES = [
  { id: 'model', label: 'Actual-model study', figure: '32/32 refreshed' },
  { id: 'retail', label: 'Retail benchmark', figure: '38/38 refreshed' },
  { id: 'budget', label: 'Fixed-budget diagnostic', figure: 'Where every method misses' },
] as const

type StudyId = (typeof STUDIES)[number]['id']

export default function Results() {
  const [active, setActive] = useState<StudyId>('model')
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = STUDIES.findIndex(s => s.id === active)
    let next = -1
    if (e.key === 'ArrowRight') next = (i + 1) % STUDIES.length
    else if (e.key === 'ArrowLeft') next = (i - 1 + STUDIES.length) % STUDIES.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = STUDIES.length - 1
    if (next < 0) return
    e.preventDefault()
    setActive(STUDIES[next].id)
    tabRefs.current[next]?.focus()
  }

  return (
    <section id="results" className="section results-section" aria-labelledby="results-title">
      <div className="wrap">
        <SectionHead
          id="results-title"
          title="Verified results"
          lede="Three frozen studies with saved evidence you can re-check offline. In the two main studies, ProofFlow refreshed every recoverable affected report with far less input than full context. Where it ties or loses, that is shown too."
        />

        <div className="rs-tabs" role="tablist" aria-label="Studies" onKeyDown={onKey}>
          {STUDIES.map((s, i) => {
            const selected = s.id === active
            return (
              <button
                key={s.id}
                ref={el => { tabRefs.current[i] = el }}
                type="button"
                role="tab"
                id={`rs-tab-${s.id}`}
                aria-selected={selected}
                aria-controls={`rs-panel-${s.id}`}
                tabIndex={selected ? 0 : -1}
                className="rs-tab"
                onClick={() => setActive(s.id)}
              >
                <span className="rs-tab-label">{s.label}</span>
                <span className="rs-tab-figure">{s.figure}</span>
                {selected && <motion.span layoutId="rs-tab-mark" className="rs-tab-mark" transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }} />}
              </button>
            )
          })}
        </div>

        <div role="tabpanel" id="rs-panel-model" aria-labelledby="rs-tab-model" hidden={active !== 'model'} className="rs-panel" tabIndex={0}>
          <ModelStudy />
        </div>
        <div role="tabpanel" id="rs-panel-retail" aria-labelledby="rs-tab-retail" hidden={active !== 'retail'} className="rs-panel" tabIndex={0}>
          <RetailStudy />
        </div>
        <div role="tabpanel" id="rs-panel-budget" aria-labelledby="rs-tab-budget" hidden={active !== 'budget'} className="rs-panel" tabIndex={0}>
          <BudgetStudy />
        </div>

        <aside className="rs-limits" aria-labelledby="rs-limits-title">
          <div className="rs-limits-head">
            <h3 id="rs-limits-title">What we don’t claim</h3>
            <p>Each limit is written in the repository next to the result it qualifies. They matter as much as the wins.</p>
          </div>
          <ul className="rs-limits-list">
            {limits.map(l => (
              <li key={l.text}>
                <p>{l.text}</p>
                <Source path={l.source} />
              </li>
            ))}
          </ul>
        </aside>

        <div className="rs-foot">
          <div className="rs-record">
            <h3>Also on record</h3>
            <ul>
              {onRecord.map(r => (
                <li key={r.text}>
                  <p>{r.text}</p>
                  <span className="rs-sources">{r.sources.map(s => <Source key={s} path={s} />)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rs-verify">
            <h3>Check it without trusting us</h3>
            <p>{verifier.text}</p>
            <div className="rs-verify-actions">
              <ButtonLink href={links.publicEvidence} external icon={<ShieldCheck aria-hidden size={18} strokeWidth={2} />}>
                Verify the evidence yourself
              </ButtonLink>
              <Source path={verifier.source} />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function Scope({ items }: { items: readonly { value: string; label: string }[] }) {
  return (
    <dl className="rs-scope">
      {items.map(it => (
        <div key={it.label}>
          <dt className="figure">{it.value}</dt>
          <dd>{it.label}</dd>
        </div>
      ))}
    </dl>
  )
}

function ModelStudy() {
  const m = modelStudy
  return (
    <div className="rs-study">
      <div className="rs-summary">
        <h3 className="rs-study-title">A real model planned it, and every affected report refreshed</h3>
        <p className="rs-hero"><span className="rs-hero-num">32/32</span><span className="rs-hero-label">affected reports refreshed</span></p>
        <p className="rs-text">
          Fable 5.2 planned each refresh from ProofFlow’s dependency evidence and matched full context, at{' '}
          <strong>{m.exposure.pct}</strong> of its provider input exposure, excluding the no-op case.
        </p>
        <Scope items={[
          { value: '48', label: 'model invocations' },
          { value: '8', label: 'fresh cases' },
          { value: '1', label: 'sample per method and case' },
          { value: '1', label: 'shared safe executor' },
        ]} />
      </div>
      <figure className="rs-figure">
        <BarChart
          rows={m.rows.map(r => ({ ...r, extra: r.correction }))}
          max={m.of}
          ticks={[0, 8, 16, 24, 32]}
          title={<>Affected reports refreshed <span className="soft">out of {m.of}</span></>}
          unit="Reports refreshed"
          tableCaption="Affected reports refreshed out of 32 in the actual-model study, by method"
          extraColumn="Correction cases completed"
        />
        <p className="rs-note">Compared methods got each case’s graph evidence allowance; full context was uncapped. Every method blocked {m.unavailableBlocked} unavailable reports.</p>
        <ShareBars
          title={<>Provider input exposure <span className="soft">cases M01–M07</span></>}
          fullLabel="Full context"
          full={m.exposure.full}
          partLabel="ProofFlow graph"
          part={m.exposure.graph}
          share={m.exposure.pct}
          shareValue={m.exposure.pctValue}
          unit="tokens"
          summary={`ProofFlow graph used ${m.exposure.graph.toLocaleString('en-US')} of the ${m.exposure.full.toLocaleString('en-US')} input tokens full context used, ${m.exposure.pct}.`}
        />
        <p className="rs-note">Counts uncached input, cache writes and cache reads. Including the no-op case M08, the ratio is {m.exposure.pctWithNoop}.</p>
        <figcaption className="rs-cite">
          <Source path={m.source} />
          <Source path={m.sourceSummary} />
        </figcaption>
      </figure>
    </div>
  )
}

function RetailStudy() {
  const r = retail
  return (
    <div className="rs-study">
      <div className="rs-summary">
        <h3 className="rs-study-title">A deterministic benchmark on real retail data</h3>
        <p className="rs-hero"><span className="rs-hero-num">{r.refreshed}</span><span className="rs-hero-label">recoverable affected reports refreshed</span></p>
        <p className="rs-text">
          {r.lines} UCI Online Retail lines, ten authored changes, registered tools doing the arithmetic. No LLM is involved.
        </p>
        <Scope items={[
          { value: r.blocked, label: 'unavailable reports correctly blocked' },
          { value: r.fewerPct, label: 'fewer evidence tokens than full context' },
        ]} />
      </div>
      <figure className="rs-figure">
        <p className="rs-chart-title">Same per-case evidence allowance as the graph <span className="soft">0 to {r.allowanceMax} tokens</span></p>
        <RetailTable
          rows={r.rows}
          of={r.of}
          caption="Retail benchmark comparators at the graph's per-case evidence allowance"
        />
        <p className="rs-note">10/10 correct endstates includes an expected refusal and a no-op, not ten newly completed answers.</p>
        <ShareBars
          title={<>Evidence tokens <span className="soft">all ten cases</span></>}
          fullLabel="Full context"
          full={r.fullTokens}
          partLabel="ProofFlow graph"
          part={r.graphTokens}
          share={r.ratioPct}
          shareValue={r.ratioValue}
          unit="tokens"
          summary={`ProofFlow graph used ${r.graphTokens.toLocaleString('en-US')} evidence tokens versus ${r.fullTokens.toLocaleString('en-US')} for full context: ${r.ratioPct} of full context, ${r.fewerPct} fewer.`}
        />
        <p className="rs-note">{r.ratioPct} of full context, so {r.fewerPct} fewer. Graph, exact-flat and full context each ran 101 tools; the saving is evidence tokens, not tool calls.</p>
        <figcaption className="rs-cite">
          <Source path={r.source} />
          <Source path={r.sourceSummary} />
        </figcaption>
      </figure>
    </div>
  )
}

function BudgetStudy() {
  const f = fixedBudget
  return (
    <div className="rs-study">
      <div className="rs-summary">
        <h3 className="rs-study-title">Under a hard cap, every method misses reports</h3>
        <p className="rs-text">
          The same eight cases, rerun with a deterministic reader and a fixed receipt-token budget. Every capped method missed
          reports at both limits. At {f.high} tokens, iterative hybrid refreshed one more report than ProofFlow.
        </p>
        <Scope items={[
          { value: '27/32', label: `ProofFlow at ${f.high} tokens` },
          { value: '28/32', label: `iterative hybrid at ${f.high} tokens` },
          { value: '32/32', label: 'uncapped reference' },
        ]} />
      </div>
      <figure className="rs-figure">
        <p className="rs-chart-title">Fresh affected reports at two caps <span className="soft">out of {f.of}</span></p>
        <Dumbbell
          rows={f.rows}
          max={f.of}
          low={f.low}
          high={f.high}
          uncapped={f.uncapped}
          ticks={[0, 8, 16, 24, 32]}
          caption="Fresh affected reports out of 32 at 4,096 and 8,192 receipt tokens, by method"
        />
        <p className="rs-note">ProofFlow graph and exact-flat produced byte-identical contexts at each cap, so they share a row.</p>
        <figcaption className="rs-cite">
          <Source path={f.source} />
        </figcaption>
      </figure>
    </div>
  )
}
