import { useState, type FormEvent, type ReactNode } from 'react'
import { ArrowRight, ChevronDown, Repeat2, ShoppingBag, SlidersHorizontal, Ticket, Undo2, Unplug } from 'lucide-react'
import { SOURCE_NAMES, type ChangePayload, type SourceName } from './engine'
import { SOURCE_LABEL, type Slot } from './model'

export type FormId = 'fx' | 'order' | 'refund' | 'support' | 'remove'
export interface FieldError { form: FormId; message: string }

/** Parse "12.5" / "-3.25" into integer cents without floating-point arithmetic. */
function parseCents(raw: string): number | null {
  const match = /^\s*([+-−])?(\d{1,6})(?:\.(\d{1,2}))?\s*$/.exec(raw)
  if (!match) return null
  const cents = Number(match[2]) * 100 + Number((match[3] ?? '').padEnd(2, '0'))
  return match[1] === '-' || match[1] === '−' ? -cents : cents
}

const slotOf = (name: SourceName) => `source:${name}` as Slot

function Chip({ icon, label, value, source, disabled, onClick, onPreview, expanded, ariaLabel }: {
  icon: ReactNode; label: string; value: ReactNode; source: SourceName | null; disabled?: boolean
  onClick: () => void; onPreview: (slot: Slot | null) => void; expanded?: boolean; ariaLabel: string
}) {
  const enter = () => source && !disabled && onPreview(slotOf(source))
  const leave = () => onPreview(null)
  return (
    <button type="button" className="demo-chip" disabled={disabled} aria-label={ariaLabel}
      aria-expanded={expanded} onClick={onClick}
      onPointerEnter={enter} onPointerLeave={leave} onFocus={enter} onBlur={leave}>
      <span className="demo-chip-icon" aria-hidden>{icon}</span>
      <span className="demo-chip-text">
        <span className="demo-chip-label">{label}</span>
        <span className="demo-chip-value figure">{value}</span>
      </span>
      {expanded !== undefined && <ChevronDown className="demo-chip-caret" size={16} strokeWidth={2.2} aria-hidden />}
    </button>
  )
}

function Field({ id, label, hint, error, disabled, onSubmit, children }: {
  id: FormId; label: string; hint: string; error: string | null; disabled: boolean
  onSubmit: () => void; children: ReactNode
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!disabled) onSubmit()
  }
  return (
    <form className="demo-field" onSubmit={submit} noValidate>
      <label htmlFor={`demo-input-${id}`}>{label}</label>
      <div className="demo-field-row">
        {children}
        <button type="submit" className="demo-field-go" disabled={disabled} aria-label={`Apply ${label.toLowerCase()}`}>
          <ArrowRight size={16} strokeWidth={2.4} aria-hidden />
        </button>
      </div>
      <span className="demo-hint figure" id={`demo-hint-${id}`}>{hint}</span>
      {error && <span className="sr-only" id={`demo-error-${id}`}>{error}</span>}
    </form>
  )
}

export default function Chips({ rate, removed, error, onChange, onFieldError, onPreview }: {
  rate: string
  removed: Set<SourceName>
  error: FieldError | null
  onChange: (payload: ChangePayload, form: FormId) => void
  onFieldError: (error: FieldError) => void
  onPreview: (slot: Slot | null) => void
}) {
  const [picking, setPicking] = useState(false)
  const [custom, setCustom] = useState(false)
  const [fx, setFx] = useState('1.20')
  const [order, setOrder] = useState('100.00')
  const [refund, setRefund] = useState('100.00')
  const [tickets, setTickets] = useState('1')
  const nextRate = rate === '1.20' ? '1.10' : '1.20'
  const off = (name: SourceName) => removed.has(name)

  const errorFor = (form: FormId) => (error?.form === form ? error.message : null)
  const described = (form: FormId) => `demo-hint-${form}${errorFor(form) ? ` demo-error-${form}` : ''}`

  const submitFx = () => {
    const match = /^\s*(\d{1,2})(?:\.(\d{1,2}))?\s*$/.exec(fx)
    if (!match) return onFieldError({ form: 'fx', message: 'Enter a rate between 0.10 and 5.00, with up to two decimals.' })
    onChange({ kind: 'fx', value: `${Number(match[1])}.${(match[2] ?? '').padEnd(2, '0')}` }, 'fx')
  }
  const submitDelta = (kind: 'order' | 'refund', raw: string) => {
    const cents = parseCents(raw)
    if (cents === null || cents < -50000 || cents > 50000) return onFieldError({ form: kind, message: 'Enter an amount between −500.00 and 500.00 EUR.' })
    if (cents === 0) return onFieldError({ form: kind, message: 'Enter a non-zero amount; zero would not change the source.' })
    onChange({ kind, delta_cents: cents }, kind)
  }
  const submitTickets = () => {
    const count = Number(tickets)
    if (!Number.isInteger(count) || count < 1 || count > 5) return onFieldError({ form: 'support', message: 'Add between 1 and 5 tickets.' })
    onChange({ kind: 'support', count }, 'support')
  }

  return (
    <div className="demo-controls">
      <div className="demo-chips" role="group" aria-label="Corrections">
        <Chip icon={<Repeat2 size={20} strokeWidth={2} />} label="EUR rate"
          value={<>{rate}<ArrowRight className="demo-chip-arrow" size={15} strokeWidth={2.4} aria-hidden />{nextRate}</>}
          source="fx" disabled={off('fx')} onPreview={onPreview}
          ariaLabel={`Correct the EUR to USD rate from ${rate} to ${nextRate}`}
          onClick={() => onChange({ kind: 'fx', value: nextRate }, 'fx')} />
        <Chip icon={<ShoppingBag size={20} strokeWidth={2} />} label="EU order" value="+€100"
          source="orders" disabled={off('orders')} onPreview={onPreview}
          ariaLabel="Add 100 euros to the first EU order"
          onClick={() => onChange({ kind: 'order', delta_cents: 10000 }, 'order')} />
        <Chip icon={<Undo2 size={20} strokeWidth={2} />} label="EU refund" value="+€100"
          source="refunds" disabled={off('refunds')} onPreview={onPreview}
          ariaLabel="Add 100 euros to that order's refund"
          onClick={() => onChange({ kind: 'refund', delta_cents: 10000 }, 'refund')} />
        <Chip icon={<Ticket size={20} strokeWidth={2} />} label="EU tickets" value="+1"
          source="tickets" disabled={off('tickets')} onPreview={onPreview}
          ariaLabel="Add one EU support ticket"
          onClick={() => onChange({ kind: 'support', count: 1 }, 'support')} />
        <Chip icon={<Unplug size={20} strokeWidth={2} />} label="A source" value="Remove"
          source={null} disabled={removed.size === SOURCE_NAMES.length} onPreview={onPreview}
          expanded={picking} ariaLabel="Remove a source"
          onClick={() => setPicking(open => !open)} />
      </div>

      {picking && (
        <div className="demo-picks" role="group" aria-label="Choose a source to remove">
          {SOURCE_NAMES.map(name => (
            <button key={name} type="button" className="demo-pick" disabled={off(name)}
              onPointerEnter={() => onPreview(slotOf(name))} onPointerLeave={() => onPreview(null)}
              onFocus={() => onPreview(slotOf(name))} onBlur={() => onPreview(null)}
              onClick={() => { onPreview(null); onChange({ kind: 'remove', source: name }, 'remove') }}>
              <Unplug size={14} strokeWidth={2.2} aria-hidden />
              {SOURCE_LABEL[name]}
            </button>
          ))}
        </div>
      )}

      <button type="button" className="demo-custom-toggle" aria-expanded={custom} aria-controls="demo-custom"
        onClick={() => setCustom(open => !open)}>
        <SlidersHorizontal size={15} strokeWidth={2.2} aria-hidden />
        Custom values
      </button>

      {custom && (
        <div className="demo-custom" id="demo-custom">
          <Field id="fx" label="EUR rate" hint="0.10 – 5.00" error={errorFor('fx')} disabled={off('fx')} onSubmit={submitFx}>
            <input id="demo-input-fx" className="demo-input figure" type="text" inputMode="decimal" value={fx}
              placeholder="1.20" onChange={event => setFx(event.target.value)} disabled={off('fx')}
              aria-invalid={!!errorFor('fx')} aria-describedby={described('fx')} />
          </Field>
          <Field id="order" label="EU order, €" hint="± 500.00" error={errorFor('order')} disabled={off('orders')}
            onSubmit={() => submitDelta('order', order)}>
            <input id="demo-input-order" className="demo-input figure" type="text" inputMode="decimal" value={order}
              placeholder="100.00" onChange={event => setOrder(event.target.value)} disabled={off('orders')}
              aria-invalid={!!errorFor('order')} aria-describedby={described('order')} />
          </Field>
          <Field id="refund" label="EU refund, €" hint="± 500.00" error={errorFor('refund')} disabled={off('refunds')}
            onSubmit={() => submitDelta('refund', refund)}>
            <input id="demo-input-refund" className="demo-input figure" type="text" inputMode="decimal" value={refund}
              placeholder="100.00" onChange={event => setRefund(event.target.value)} disabled={off('refunds')}
              aria-invalid={!!errorFor('refund')} aria-describedby={described('refund')} />
          </Field>
          <Field id="support" label="EU tickets" hint="1 – 5" error={errorFor('support')} disabled={off('tickets')} onSubmit={submitTickets}>
            <input id="demo-input-support" className="demo-input figure" type="text" inputMode="numeric" value={tickets}
              placeholder="1" onChange={event => setTickets(event.target.value)} disabled={off('tickets')}
              aria-invalid={!!errorFor('support')} aria-describedby={described('support')} />
          </Field>
        </div>
      )}
      {error && <p className="demo-error" role="alert">{error.message}</p>}
    </div>
  )
}
