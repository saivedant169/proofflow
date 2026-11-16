import { useState, type FormEvent, type ReactNode } from 'react'
import { CircleCheck, CircleX, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react'
import { Button } from '../../components/ui'
import { SOURCE_NAMES, type ChangePayload, type SourceName, type Verification } from './engine'
import { SOURCE_LABEL, type View } from './model'

export type FormId = 'fx' | 'order' | 'refund' | 'support' | 'remove'
export interface FieldError { form: FormId; message: string }

/** Parse "12.5" / "-3.25" into integer cents without floating-point arithmetic. */
function parseCents(raw: string): number | null {
  const match = /^\s*([+-])?(\d{1,6})(?:\.(\d{1,2}))?\s*$/.exec(raw)
  if (!match) return null
  const cents = Number(match[2]) * 100 + Number((match[3] ?? '').padEnd(2, '0'))
  return match[1] === '-' ? -cents : cents
}

function Fix({ id, title, hint, error, disabled, children, onSubmit, action = 'Apply' }: {
  id: FormId; title: string; hint: ReactNode; error: string | null; disabled: boolean
  children: ReactNode; onSubmit: () => void; action?: string
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!disabled) onSubmit()
  }
  return (
    <form className={`demo-fix${disabled ? ' is-disabled' : ''}`} onSubmit={submit} noValidate aria-labelledby={`demo-fix-${id}`}>
      <label className="demo-fix-title" id={`demo-fix-${id}`} htmlFor={`demo-input-${id}`}>{title}</label>
      <div className="demo-fix-row">
        {children}
        <button type="submit" className="demo-apply" disabled={disabled}>{action}</button>
      </div>
      <p className="demo-fix-hint" id={`demo-hint-${id}`}>{hint}</p>
      {error && <p className="demo-fix-error" id={`demo-error-${id}`} role="alert">{error}</p>}
    </form>
  )
}

export default function Console({ view, removed, error, verification, onChange, onFieldError, onRefresh, onVerify, onReset }: {
  view: View
  removed: Set<SourceName>
  error: FieldError | null
  verification: Verification | null
  onChange: (payload: ChangePayload, form: FormId) => void
  onFieldError: (error: FieldError) => void
  onRefresh: () => void
  onVerify: () => void
  onReset: () => void
}) {
  const [fx, setFx] = useState('1.20')
  const [order, setOrder] = useState('100.00')
  const [refund, setRefund] = useState('100.00')
  const [tickets, setTickets] = useState('1')
  const firstAvailable = SOURCE_NAMES.find(name => !removed.has(name)) ?? 'fx'
  const [source, setSource] = useState<SourceName>('fx')
  const removeChoice = removed.has(source) ? firstAvailable : source

  const errorFor = (form: FormId) => (error?.form === form ? error.message : null)
  const described = (form: FormId) => `demo-hint-${form}${errorFor(form) ? ` demo-error-${form}` : ''}`
  const nodes = view.nodes

  const submitFx = () => {
    const match = /^\s*(\d{1,2})(?:\.(\d{1,2}))?\s*$/.exec(fx)
    if (!match) return onFieldError({ form: 'fx', message: 'Enter a rate between 0.10 and 5.00, with up to two decimals.' })
    onChange({ kind: 'fx', value: `${Number(match[1])}.${(match[2] ?? '').padEnd(2, '0')}` }, 'fx')
  }
  const submitDelta = (kind: 'order' | 'refund', raw: string) => {
    const cents = parseCents(raw)
    if (cents === null || cents < -50000 || cents > 50000) {
      return onFieldError({ form: kind, message: 'Enter an amount between −500.00 and 500.00 EUR.' })
    }
    if (cents === 0) return onFieldError({ form: kind, message: 'Enter a non-zero amount; zero would not change the source.' })
    onChange({ kind, delta_cents: cents }, kind)
  }

  return (
    <aside className="demo-console" aria-labelledby="demo-console-title">
      <h3 className="demo-panel-title" id="demo-console-title">Corrections</h3>
      <p className="demo-fine">The five corrections the live app accepts, with the same bounds.</p>

      <div className="demo-fixes">
        <Fix id="fx" title="Exchange rate, EUR → USD" error={errorFor('fx')} disabled={removed.has('fx')} onSubmit={submitFx}
          hint={removed.has('fx') ? 'Source removed. Reset the sample to restore it.' : <>Saved rate {nodes['source:fx'].detail.replace('EUR ', '')}. Range 0.10 to 5.00.</>}>
          <input id="demo-input-fx" className="demo-input figure" type="text" inputMode="decimal" value={fx}
            onChange={event => setFx(event.target.value)} disabled={removed.has('fx')}
            aria-invalid={!!errorFor('fx')} aria-describedby={described('fx')} />
        </Fix>

        <Fix id="order" title="Adjust the first EU order, EUR" error={errorFor('order')} disabled={removed.has('orders')}
          onSubmit={() => submitDelta('order', order)}
          hint={removed.has('orders') ? 'Source removed. Reset the sample to restore it.' : <>Order eu-101 is {nodes['source:orders'].detail.replace('eu-101 ', '')}. Adds this amount; negative subtracts.</>}>
          <input id="demo-input-order" className="demo-input figure" type="text" inputMode="decimal" value={order}
            onChange={event => setOrder(event.target.value)} disabled={removed.has('orders')}
            aria-invalid={!!errorFor('order')} aria-describedby={described('order')} />
        </Fix>

        <Fix id="refund" title="Adjust that order’s refund, EUR" error={errorFor('refund')} disabled={removed.has('refunds')}
          onSubmit={() => submitDelta('refund', refund)}
          hint={removed.has('refunds') ? 'Source removed. Reset the sample to restore it.' : <>Its refund is {nodes['source:refunds'].detail.replace('eu-101 ', '')}. Range ±500.00.</>}>
          <input id="demo-input-refund" className="demo-input figure" type="text" inputMode="decimal" value={refund}
            onChange={event => setRefund(event.target.value)} disabled={removed.has('refunds')}
            aria-invalid={!!errorFor('refund')} aria-describedby={described('refund')} />
        </Fix>

        <Fix id="support" title="Add EU support tickets" error={errorFor('support')} disabled={removed.has('tickets')} action="Add"
          onSubmit={() => onChange({ kind: 'support', count: Number(tickets) }, 'support')}
          hint={removed.has('tickets') ? 'Source removed. Reset the sample to restore it.' : <>{nodes['source:tickets'].detail.replace('EU ', 'EU has ')} now. Adds 1 to 5.</>}>
          <select id="demo-input-support" className="demo-input figure" value={tickets} onChange={event => setTickets(event.target.value)}
            disabled={removed.has('tickets')} aria-describedby={described('support')}>
            {[1, 2, 3, 4, 5].map(count => <option key={count} value={String(count)}>{count}</option>)}
          </select>
        </Fix>

        <Fix id="remove" title="Remove a source" error={errorFor('remove')} disabled={removed.size === SOURCE_NAMES.length} action="Remove"
          onSubmit={() => onChange({ kind: 'remove', source: removeChoice }, 'remove')}
          hint="Work that read it is blocked until you reset.">
          <select id="demo-input-remove" className="demo-input" value={removeChoice}
            onChange={event => setSource(event.target.value as SourceName)} aria-describedby={described('remove')}
            disabled={removed.size === SOURCE_NAMES.length}>
            {SOURCE_NAMES.map(name => (
              <option key={name} value={name} disabled={removed.has(name)}>{SOURCE_LABEL[name]}{removed.has(name) ? ' (removed)' : ''}</option>
            ))}
          </select>
        </Fix>
      </div>

      <div className="demo-actions">
        <Button onClick={onRefresh} icon={<RefreshCw size={17} strokeWidth={2.2} aria-hidden />}>Refresh affected</Button>
        <div className="demo-actions-row">
          <Button variant="secondary" onClick={onVerify} icon={<ShieldCheck size={17} strokeWidth={2} aria-hidden />}>Check values</Button>
          <Button variant="quiet" onClick={onReset} icon={<RotateCcw size={16} strokeWidth={2} aria-hidden />}>Reset sample</Button>
        </div>
      </div>

      {verification && (
        <div className={`demo-verify ${verification.passed ? 'is-pass' : 'is-fail'}`}>
          <p className="demo-verify-title">
            {verification.passed ? <CircleCheck size={17} aria-hidden /> : <CircleX size={17} aria-hidden />}
            {verification.passed ? 'Check passed' : 'Check failed'}
          </p>
          <ul>
            {verification.reports.map(row => (
              <li key={row.id}>
                <strong>{row.title}</strong>{' '}
                {row.error ? 'cannot be recomputed: a source it needs was removed.'
                  : !row.numericMatch ? `saved values differ from a fresh recomputation (${row.state === 'current' ? 'current' : 'needs refresh'}).`
                    : row.state !== 'current' ? 'values happen to match, but an input changed, so it still needs refresh.'
                      : 'is current and matches a fresh recomputation.'}
              </li>
            ))}
          </ul>
          <p className="demo-fine">Recomputes each report from current sources without the graph or cached results, like <code>/api/verify</code>.</p>
        </div>
      )}
    </aside>
  )
}
