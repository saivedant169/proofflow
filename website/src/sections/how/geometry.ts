/** Tiny geometry helpers for the thread diagrams: cubic edges between box anchors. */

export interface Box { x: number; y: number; w: number; h: number }
export type Side = 'left' | 'right' | 'top' | 'bottom'
export interface EdgeGeometry { d: string; mid: { x: number; y: number }; horizontal: boolean; span: number }

const clamp = (v: number, limit: number) => Math.max(-limit, Math.min(limit, v))

function anchor(box: Box, side: Side, other: Box) {
  switch (side) {
    case 'right': return { x: box.x + box.w / 2, y: box.y + clamp((other.y - box.y) * 0.35, box.h / 2 - 12), nx: 1, ny: 0 }
    case 'left': return { x: box.x - box.w / 2, y: box.y + clamp((other.y - box.y) * 0.35, box.h / 2 - 12), nx: -1, ny: 0 }
    case 'bottom': return { x: box.x + clamp((other.x - box.x) * 0.6, box.w / 2 - 16), y: box.y + box.h / 2, nx: 0, ny: 1 }
    case 'top': return { x: box.x + clamp((other.x - box.x) * 0.6, box.w / 2 - 16), y: box.y - box.h / 2, nx: 0, ny: -1 }
  }
}

/**
 * Edge from box a to box b. `axis` is the layout's reading direction; edges follow it unless the
 * two boxes are aligned on that axis, in which case they run across it.
 */
export function edgeGeometry(a: Box, b: Box, axis: 'x' | 'y', sides?: [Side, Side]): EdgeGeometry {
  let fromSide: Side
  let toSide: Side
  if (sides) {
    ;[fromSide, toSide] = sides
  } else {
    const horizontal = axis === 'x' ? Math.abs(b.x - a.x) >= 40 : Math.abs(b.y - a.y) < 40
    if (horizontal) {
      fromSide = b.x >= a.x ? 'right' : 'left'
      toSide = b.x >= a.x ? 'left' : 'right'
    } else {
      fromSide = b.y >= a.y ? 'bottom' : 'top'
      toSide = b.y >= a.y ? 'top' : 'bottom'
    }
  }
  const s = anchor(a, fromSide, b)
  const e = anchor(b, toSide, a)
  const k1 = Math.max(24, (s.nx ? Math.abs(e.x - s.x) : Math.abs(e.y - s.y)) * 0.5)
  const k2 = Math.max(24, (e.nx ? Math.abs(e.x - s.x) : Math.abs(e.y - s.y)) * 0.5)
  const c1 = { x: s.x + s.nx * k1, y: s.y + s.ny * k1 }
  const c2 = { x: e.x + e.nx * k2, y: e.y + e.ny * k2 }
  const r = (n: number) => Math.round(n * 10) / 10
  const d = `M${r(s.x)} ${r(s.y)} C${r(c1.x)} ${r(c1.y)} ${r(c2.x)} ${r(c2.y)} ${r(e.x)} ${r(e.y)}`
  const mid = { x: (s.x + 3 * c1.x + 3 * c2.x + e.x) / 8, y: (s.y + 3 * c1.y + 3 * c2.y + e.y) / 8 }
  const horizontal = fromSide === 'left' || fromSide === 'right'
  const span = horizontal ? Math.abs(e.x - s.x) : Math.abs(e.y - s.y)
  return { d, mid, horizontal, span }
}
