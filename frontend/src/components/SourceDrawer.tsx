import { useState } from 'react'
import { Calculator, CircleAlert, Database, Headphones, Info, LoaderCircle, RotateCcw } from 'lucide-react'
import type { SourceChange, SourceName, WorkspaceState } from '../lib/types'
import Drawer from './Drawer'

const options = [
  { kind: 'fx', title: 'Exchange rate', description: 'The EUR → USD rate used in revenue calculations', icon: Database },
  { kind: 'order', title: 'Order amount', description: 'Correct an order in the transaction data', icon: Calculator },
  { kind: 'refund', title: 'Refund amount', description: 'Correct the refund matched to that order', icon: RotateCcw },
  { kind: 'support', title: 'Support tickets', description: 'Add tickets to the independent support branch', icon: Headphones },
  { kind: 'remove', title: 'Missing source', description: 'Make an input unavailable and test refusal', icon: CircleAlert },
] as const

export default function SourceDrawer({ state, onClose, onApply, busy }: { state: WorkspaceState; onClose: () => void; onApply: (change: SourceChange) => Promise<void>; busy: boolean }) {
  const [kind, setKind] = useState<SourceChange['kind']>('fx')
  const [value, setValue] = useState('1.20')
  const [amount, setAmount] = useState('100.00')
  const [count, setCount] = useState('1')
  const [source, setSource] = useState<SourceName>('fx')
  const [error, setError] = useState<string | null>(null)
  const fx = state.dataset.sources.find(item => item.name === 'fx')
  const currentFX = fx?.removed ? 'Unavailable' : String(fx?.summary.EUR ?? 'Unavailable')
  const selected = options.find(option => option.kind === kind)!
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError(null)
    let change: SourceChange
    if (kind === 'fx') change = { kind, value }
    else if (kind === 'order' || kind === 'refund') change = { kind, delta_cents: Math.round(Number(amount) * 100) }
    else if (kind === 'support') change = { kind, count: Number(count) }
    else change = { kind, source }
    try { await onApply(change); onClose() } catch (cause) { setError(cause instanceof Error ? cause.message : 'The correction could not be applied.') }
  }
  return <Drawer title="Change a source" subtitle="Make a correction. Follow its consequences." onClose={onClose}><form onSubmit={submit} className="source-form">
    <div className="source-options" role="radiogroup" aria-label="Source to correct">{options.map((option, index) => <button type="button" key={option.kind} className={`source-option ${kind === option.kind ? 'selected' : ''}`} role="radio" aria-checked={kind === option.kind} tabIndex={kind === option.kind ? 0 : -1} onKeyDown={event => {
      if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return
      event.preventDefault()
      const next = (index + (['ArrowDown', 'ArrowRight'].includes(event.key) ? 1 : -1) + options.length) % options.length
      setKind(options[next].kind); setError(null)
      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button')[next]?.focus()
    }} onClick={() => { setKind(option.kind); setError(null) }} disabled={busy}>
      <option.icon size={22} /><span><strong>{option.title}</strong><small>{option.description}</small></span><i className="radio-dot" />
    </button>)}</div>
    <div className="source-editor"><h3>{selected.title}</h3>
      {kind === 'fx' && <><label htmlFor="fx-value">EUR → USD</label><div className="source-input-row"><div className="current-source"><span>Current</span><strong>{currentFX}</strong></div><input id="fx-value" type="number" step="0.01" min="0.01" max="10" value={value} onChange={event => setValue(event.target.value)} required disabled={busy} /></div></>}
      {(kind === 'order' || kind === 'refund') && <><label htmlFor="amount-value">Adjustment to the first EU {kind === 'order' ? 'order' : 'refund'} · EUR</label><input id="amount-value" type="number" step="0.01" min="-10000" max="10000" value={amount} onChange={event => setAmount(event.target.value)} required disabled={busy} /><small className="input-help">Adds this amount to the saved source value. Negative values subtract.</small></>}
      {kind === 'support' && <><label htmlFor="ticket-value">New EU tickets</label><input id="ticket-value" type="number" min="1" max="5" step="1" value={count} onChange={event => setCount(event.target.value)} required disabled={busy} /></>}
      {kind === 'remove' && <><label htmlFor="missing-source">Source to make unavailable</label><select id="missing-source" value={source} onChange={event => setSource(event.target.value as SourceName)} disabled={busy}><option value="fx">Exchange rates</option><option value="orders">Orders</option><option value="refunds">Refunds</option><option value="tickets">Support tickets</option></select><small className="input-help">Dependent claims will be blocked. Start a new workspace to restore the fixture.</small></>}
      <p className="field-note"><Info size={16} /><span>Only calculations that consumed this source need revalidation.</span></p>
    </div>
    {error && <div role="alert" className="inline-error">{error}</div>}
    <button className="button button-primary full-width" disabled={busy} type="submit">{busy ? <><LoaderCircle size={17} className="spin" />Applying correction…</> : 'Apply correction'}</button>
    <p className="drawer-footer">Changes stay in this browser workspace.</p>
  </form></Drawer>
}
