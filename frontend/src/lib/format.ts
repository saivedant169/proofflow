import type { Claim, JSONValue } from './types'

const numberFormat = new Intl.NumberFormat('en-US')

export function parseUSDCents(value: unknown): bigint | null {
  if (typeof value === 'number' && Number.isSafeInteger(value)) return BigInt(value)
  if (typeof value === 'string' && /^(?:0|-?[1-9]\d*)$/.test(value)) return BigInt(value)
  return null
}

export function formatValue(value: JSONValue | undefined, unit: string): string {
  if (value === null || value === undefined) return 'Unavailable'
  if (unit === 'USD cents') {
    const cents = parseUSDCents(value)
    if (cents === null) return 'Unavailable'
    const absolute = cents < 0n ? -cents : cents
    const dollars = numberFormat.format(absolute / 100n)
    const remainder = String(absolute % 100n).padStart(2, '0')
    return `${cents < 0n ? '-' : ''}$${dollars}.${remainder}`
  }
  if (typeof value === 'number') return numberFormat.format(value)
  return typeof value === 'string' ? value : JSON.stringify(value)
}

export function claimValue(claim: Claim | undefined): string {
  return claim ? formatValue(claim.value, claim.unit) : 'Unavailable'
}

export const toolLabels: Record<string, string> = {
  gross_by_region: 'Gross sales grouped by region', refunds_by_region: 'Refunds matched to orders',
  net_by_region: 'Net revenue calculated', convert_to_usd: 'Regional revenue converted to USD',
  company_total: 'Company total calculated', support_by_region: 'Support tickets counted',
  compose_report: 'Report composed from saved results',
}
