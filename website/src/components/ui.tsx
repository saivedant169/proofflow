import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'
import { ExternalLink } from 'lucide-react'
import { repoFile } from '../content/facts'
import './ui.css'

type Variant = 'primary' | 'secondary' | 'quiet'

/** Link styled as a button. External links get an icon and open in a new tab. */
export function ButtonLink({ variant = 'primary', external, icon, children, className = '', ...rest }:
  AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant; external?: boolean; icon?: ReactNode }) {
  return (
    <a className={`btn btn-${variant} ${className}`} {...(external ? { target: '_blank', rel: 'noreferrer' } : {})} {...rest}>
      {icon}
      <span>{children}</span>
      {external && <ExternalLink aria-hidden className="btn-ext" size={15} strokeWidth={2} />}
      {external && <span className="sr-only">(opens in a new tab)</span>}
    </a>
  )
}

export function Button({ variant = 'primary', icon, children, className = '', ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; icon?: ReactNode }) {
  return (
    <button type="button" className={`btn btn-${variant} ${className}`} {...rest}>
      {icon}
      <span>{children}</span>
    </button>
  )
}

export type ClaimState = 'current' | 'stale' | 'withheld' | 'refreshed' | 'reused' | 'blocked' | 'unknown'

const STATE_LABEL: Record<ClaimState, string> = {
  current: 'Current',
  stale: 'Stale',
  withheld: 'Withheld',
  refreshed: 'Refreshed',
  reused: 'Reused',
  blocked: 'Blocked',
  unknown: 'Unknown',
}

/** State pill. Always text + shape, never color alone. */
export function StateTag({ state, children }: { state: ClaimState; children?: ReactNode }) {
  return (
    <span className={`state-tag state-${state}`}>
      <span className="state-dot" aria-hidden />
      {children ?? STATE_LABEL[state]}
    </span>
  )
}

/** Small citation link to the repository file that states a fact. */
export function Source({ path, label }: { path: string; label?: string }) {
  const first = path.split(',')[0].trim()
  return (
    <a className="source-link" href={repoFile(first)} target="_blank" rel="noreferrer">
      <span className="source-label">Source</span>
      <code>{label ?? first}</code>
    </a>
  )
}

/** Standard section header: title + optional lede. No eyebrow labels by design. */
export function SectionHead({ title, lede, id }: { title: ReactNode; lede?: ReactNode; id?: string }) {
  return (
    <header className="section-head">
      <h2 className="section-title" id={id}>{title}</h2>
      {lede && <p className="section-lede">{lede}</p>}
    </header>
  )
}

export const usd = (cents: number) =>
  (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2 })
