import type { Claim, JSONValue } from './types'

export function formatValue(value: JSONValue | undefined, unit: string): string {
  if (value === null || value === undefined) return 'Unavailable'
  if (typeof value === 'number' && unit === 'USD cents') {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value / 100)
  }
  if (typeof value === 'number') return new Intl.NumberFormat('en-US').format(value)
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
