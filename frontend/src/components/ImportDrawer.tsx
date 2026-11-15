import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, CheckCircle2, Download, FileUp, Info, LoaderCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { ImportedWorkspaceState, ImportPreview, ImportRequest } from '../lib/types'
import Drawer from './Drawer'

const MAX_BYTES = 1024 * 1024
const SAMPLE = 'order_id,region,currency,gross_cents,refund_cents,ticket_count\nUS-001,US,USD,180000,5000,2\nEU-001,EU,EUR,100000,10000,0\nUK-001,UK,GBP,80000,0,1\n'
const SAMPLE_URL = `data:text/csv;charset=utf-8,${encodeURIComponent(SAMPLE)}`

export default function ImportDrawer({ existing, initial, busy, onClose, onApply }: {
  existing: ImportedWorkspaceState | null
  initial: ImportRequest | null
  busy: boolean
  onClose: () => void
  onApply: (request: ImportRequest) => Promise<void>
}) {
  const savedRates = existing?.dataset.sources.find(source => source.name === 'fx')?.summary
  const [csv, setCSV] = useState(initial?.csv_text ?? '')
  const [eur, setEUR] = useState(initial?.rates?.EUR ?? (typeof savedRates?.EUR === 'string' ? savedRates.EUR : ''))
  const [gbp, setGBP] = useState(initial?.rates?.GBP ?? (typeof savedRates?.GBP === 'string' ? savedRates.GBP : ''))
  const [region, setRegion] = useState(existing?.dataset.selected_region ?? initial?.region ?? '')
  const [regions, setRegions] = useState<string[]>(existing?.dataset.regions ?? [])
  const [filename, setFilename] = useState('')
  const [sampleLoaded, setSampleLoaded] = useState(false)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [validated, setValidated] = useState<ImportRequest | null>(null)
  const [validating, setValidating] = useState(false)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const file = useRef<HTMLInputElement>(null)
  const alert = useRef<HTMLDivElement>(null)
  const abort = useRef<AbortController | null>(null)
  const fileSequence = useRef(0)
  const locked = busy || validating || reading
  useEffect(() => () => { abort.current?.abort(); fileSequence.current++ }, [])
  useEffect(() => { if (error) alert.current?.focus() }, [error])

  function invalidate() { setPreview(null); setValidated(null); setError(null) }
  function detachSampleRates() {
    if (sampleLoaded && !existing) { setEUR(''); setGBP(''); setRegion(''); setSampleLoaded(false) }
  }
  function changeCSV(value: string) {
    invalidate(); setFilename(''); setRegions([])
    if (new TextEncoder().encode(value).length > MAX_BYTES) {
      setError('CSV exceeds 1 MiB. Choose a smaller file or paste fewer rows.'); return
    }
    detachSampleRates(); setCSV(value)
  }
  async function readFile(selected: File | undefined) {
    if (!selected) return
    invalidate()
    if (selected.size > MAX_BYTES) { setError('CSV exceeds 1 MiB. Choose a smaller file.'); return }
    const sequence = ++fileSequence.current
    setReading(true)
    try {
      const value = new TextDecoder('utf-8', { fatal: true }).decode(await selected.arrayBuffer())
      if (sequence !== fileSequence.current) return
      detachSampleRates(); setCSV(value); setFilename(selected.name); setRegions([])
    } catch {
      if (sequence === fileSequence.current) setError('This file could not be read as UTF-8 CSV. Export it as UTF-8 and try again.')
    } finally { if (sequence === fileSequence.current) setReading(false) }
  }
  function useSample() {
    invalidate(); setCSV(SAMPLE); setEUR('1.10'); setGBP('1.25'); setFilename('Authored sample CSV'); setRegions([]); setSampleLoaded(true)
    if (!existing) setRegion('EU')
  }
  async function validate() {
    setError(null); setValidating(true)
    const controller = new AbortController()
    abort.current = controller
    const request: ImportRequest = { csv_text: csv, rates: { ...(eur ? { EUR: eur } : {}), ...(gbp ? { GBP: gbp } : {}) }, ...(region ? { region } : {}) }
    try {
      const result = await api.previewImport(request, { signal: controller.signal })
      setPreview(result); setRegion(result.selected_region); setRegions(result.regions)
      setValidated({ ...request, region: result.selected_region })
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'The CSV could not be validated.')
    } finally { if (!controller.signal.aborted) setValidating(false) }
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (locked) return
    if (!validated || !preview) { await validate(); return }
    setError(null)
    try { await onApply(validated); onClose() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'The import did not complete. Its latest state must be checked.') }
  }

  return <Drawer title={existing ? 'Update your CSV' : 'Use your data'} subtitle={existing ? 'Publish a correction, then follow the affected work.' : 'Two revenue reports, built from the data you supply.'} onClose={onClose} wide>
    <form className="import-form" onSubmit={submit}>
      <div className="import-scope"><Info size={17} /><p>A guided calculation: net revenue in USD for the company and your chosen region. No live model or arbitrary queries.</p></div>
      <div className="import-section-heading"><label htmlFor="import-csv">1. Supply one CSV</label><a className="text-link" href={SAMPLE_URL} download="proofflow-sample.csv"><Download size={13} />Sample CSV</a></div>
      <div className="import-file-actions"><input ref={file} className="sr-only" tabIndex={-1} type="file" accept=".csv,text/csv" aria-label="Upload UTF-8 CSV" disabled={locked} onChange={event => { void readFile(event.target.files?.[0]); event.target.value = '' }} /><button className="button button-secondary" type="button" disabled={locked} onClick={() => file.current?.click()}><FileUp size={15} />{reading ? 'Reading file…' : 'Choose file'}</button><span>{filename || 'Or paste the complete CSV below'}</span></div>
      <textarea id="import-csv" className="import-csv" value={csv} onChange={event => changeCSV(event.target.value)} disabled={locked} required spellCheck={false} autoCapitalize="off" autoCorrect="off" placeholder={'order_id,region,currency,gross_cents\norder-001,EU,EUR,10000'} aria-describedby="import-bounds" />
      <p className="input-help" id="import-bounds">UTF-8 · up to 1 MiB · 1,000 order rows · 10,000 total ticket counts</p>
      <details className="import-format"><summary>Column guide & sample</summary><p><code>order_id</code>, <code>region</code>, <code>currency</code> and <code>gross_cents</code> are required. Optional <code>refund_cents</code> and <code>ticket_count</code> default to zero when blank.</p><p>Use unique order IDs, nonnegative whole cents, and one currency per region. USD, EUR and GBP are supported. Refunds cannot exceed the order amount. Ticket counts form a separate artifact; these two reports contain revenue only.</p>{!existing && <button type="button" className="text-link" disabled={locked} onClick={useSample}>Fill with the authored sample<ArrowRight size={13} /></button>}<p className="import-sample-note">The sample uses EUR → USD 1.10 and GBP → USD 1.25. These are example rates, not market quotes.</p></details>

      <div className="import-section-heading"><h3>2. Set your exchange rates</h3><span>USD output · USD rate 1</span></div>
      <div className="import-rates"><label>EUR → USD<input value={eur} onChange={event => { invalidate(); setEUR(event.target.value) }} inputMode="decimal" placeholder="Required if used" disabled={locked} /></label><label>GBP → USD<input value={gbp} onChange={event => { invalidate(); setGBP(event.target.value) }} inputMode="decimal" placeholder="Required if used" disabled={locked} /></label></div>
      <p className="input-help">Supply USD per currency unit, greater than 0 and at most 1,000. Rates are supplied by you, not fetched.</p>
      <label className="import-region" htmlFor="import-region">Region for the second report
        {regions.length ? <select id="import-region" value={region} disabled={locked || !!existing} onChange={event => { invalidate(); setRegion(event.target.value) }}>{regions.map(item => <option key={item} value={item}>{item}</option>)}</select> : <input id="import-region" value={region} onChange={event => { invalidate(); setRegion(event.target.value) }} placeholder="Choose after validation, or enter an exact region" disabled={locked || !!existing} />}
      </label>
      {existing && <p className="input-help">This workspace keeps its selected region. Use New workspace to choose another.</p>}

      {preview && <section className="import-preview" aria-label="Validated CSV preview" aria-live="polite"><div><CheckCircle2 size={18} /><h3>Ready to {existing ? 'publish' : 'create'}</h3></div><dl><div><dt>Order rows</dt><dd>{preview.row_count.toLocaleString()}</dd></div><div><dt>Regions</dt><dd>{preview.regions.length}</dd></div><div><dt>Report region</dt><dd>{preview.selected_region}</dd></div><div><dt>Currencies</dt><dd>{preview.currencies.join(', ')}</dd></div></dl><p>{preview.accounting.preflight_calculation_count} validation calculations · {preview.accounting.recorded_tool_call_count} recorded tool calls. This preview has not changed a workspace.</p><p>{existing ? 'Publishing validates again and updates source versions. Refresh affected then recomputes stale results.' : 'Creating validates again, runs the guided recipes and checks the saved values against fresh calculations.'}</p></section>}
      {error && <div ref={alert} tabIndex={-1} role="alert" className="inline-error">{error}</div>}
      <button className="button button-primary full-width" type="submit" disabled={locked || !csv.trim()}>{locked ? <><LoaderCircle size={16} className="spin" />{validating ? 'Validating calculations…' : reading ? 'Reading CSV…' : existing ? 'Publishing correction…' : 'Creating reports…'}</> : preview ? <>{existing ? 'Publish correction' : 'Create reports'}<ArrowRight size={16} /></> : 'Validate CSV'}</button>
      <p className="drawer-footer">{existing ? 'Supply the whole CSV, including unchanged rows. Reordering alone does not change the canonical sources.' : 'CSV contents are sent to this ProofFlow server and saved as an isolated workspace.'} Validation and recorded execution counts are reported separately.</p>
    </form>
  </Drawer>
}
