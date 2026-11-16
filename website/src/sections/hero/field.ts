/**
 * Background thread field for the hero stage: long, quiet lineage lines that lean toward the pointer.
 * Deterministic (no randomness), so every render and capture is identical.
 */

export const FIELD = { w: 1440, h: 900, lines: 22 } as const

export type FieldPointer = { x: number; y: number; a: number }

const SIGMA2 = 2 * 240 * 240
const f = (n: number) => n.toFixed(1)

function attract(x: number, y: number, p: FieldPointer, kx: number, ky: number) {
  if (p.a <= 0.001) return { x, y }
  const dx = p.x - x
  const dy = p.y - y
  const w = p.a * Math.exp(-(dx * dx + dy * dy) / SIGMA2)
  return { x: x + dx * w * kx, y: y + dy * w * ky }
}

export function fieldPath(i: number, t = 0, p: FieldPointer = { x: 0, y: 0, a: 0 }): string {
  const step = (FIELD.h - 80) / (FIELD.lines - 1)
  const base = 40 + i * step
  const y0 = base + 22 * Math.sin(i * 1.3)
  const y3 = base - 26 * Math.cos(i * 0.9)
  const c1 = attract(440, base + 54 * Math.sin(i * 0.8 + t * 0.00022), p, 0.22, 0.6)
  const c2 = attract(1000, base + 54 * Math.cos(i * 0.62 + t * 0.00018), p, 0.22, 0.6)
  return `M-60 ${f(y0)} C${f(c1.x)} ${f(c1.y)} ${f(c2.x)} ${f(c2.y)} 1500 ${f(y3)}`
}
