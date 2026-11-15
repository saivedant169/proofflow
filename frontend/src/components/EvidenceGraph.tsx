import { useEffect, useMemo, useRef, useState } from 'react'
import { Calculator, Database, FileText, Headphones, MousePointer2 } from 'lucide-react'
import type { GraphNode, WorkspaceState } from '../lib/types'

type ProjectedEdge = { source: string; target: string; receipt: string }

function displayLabel(node: GraphNode) {
  if (node.kind !== 'source') return node.label
  return ({ fx: 'FX rates', orders: 'Orders', refunds: 'Refunds', tickets: 'Support tickets' } as Record<string, string>)[node.label] ?? node.label
}

function project(state: WorkspaceState, availableWidth: number) {
  const nodesById = new Map(state.graph.nodes.map(node => [node.id, node]))
  const edges: ProjectedEdge[] = []
  for (const produced of state.graph.edges.filter(edge => edge.kind === 'PRODUCED')) {
    const output = nodesById.get(produced.target)
    if (!output?.current_head) continue
    for (const consumed of state.graph.edges.filter(edge => edge.kind === 'CONSUMED' && edge.target === produced.source)) {
      if (nodesById.has(consumed.source)) edges.push({ source: consumed.source, target: produced.target, receipt: produced.source })
    }
  }
  // Some supported API versions already supply the native dependency projection.
  if (!edges.length) for (const edge of state.graph.edges) {
    if (edge.kind === 'CONSUMED' && nodesById.get(edge.target)?.kind === 'artifact') edges.push({ ...edge, receipt: '' })
  }
  const visible = new Set(edges.flatMap(edge => [edge.source, edge.target]))
  const nodes = state.graph.nodes.filter(node => visible.has(node.id) && ['source', 'artifact'].includes(node.kind))
  const ranks = new Map(nodes.map(node => [node.id, 0]))
  for (let pass = 0; pass < nodes.length; pass++) {
    let changed = false
    for (const edge of edges) {
      const next = (ranks.get(edge.source) ?? 0) + 1
      if (next > (ranks.get(edge.target) ?? 0) && next < nodes.length) { ranks.set(edge.target, next); changed = true }
    }
    if (!changed) break
  }
  const maxRank = Math.max(0, ...ranks.values())
  // Outputs share the last visual column. Edges remain the exact recorded
  // dependency pairs; this is layout only, not an invented shorter path.
  for (const report of state.reports) if (ranks.has(report.id)) ranks.set(report.id, maxRank)
  const columns = Array.from({ length: maxRank + 1 }, (_, rank) => nodes.filter(node => ranks.get(node.id) === rank).sort((a, b) => a.label.localeCompare(b.label)))
  const gap = maxRank > 4 ? 18 : 34
  const preferredNodeWidth = maxRank > 4 ? 128 : 158
  const minimumNodeWidth = maxRank > 4 ? 112 : 135
  const nodeW = Math.min(preferredNodeWidth, Math.max(minimumNodeWidth, (availableWidth - 36 - maxRank * gap) / (maxRank + 1)))
  const width = (maxRank + 1) * nodeW + maxRank * gap + 36
  const height = Math.max(340, Math.max(...columns.map(column => column.length)) * 76 + 45)
  const positions = new Map<string, { x: number; y: number }>()
  columns.forEach((column, rank) => column.forEach((node, row) => positions.set(node.id, {
    x: 18 + rank * (nodeW + gap), y: 44 + row * 76 + Math.max(0, 4 - column.length) * 25,
  })))
  return { nodes, edges, positions, width, height, nodeW, gap, maxRank }
}

function NodeIcon({ node, reportIds }: { node: GraphNode; reportIds: Set<string> }) {
  if (reportIds.has(node.id)) return <FileText size={17} />
  if (node.logical_id.includes('support') || node.logical_id.includes('tickets')) return <Headphones size={17} />
  return node.kind === 'source' ? <Database size={17} /> : <Calculator size={17} />
}

export default function EvidenceGraph({ state, onInspect }: { state: WorkspaceState; onInspect: (id: string) => void }) {
  const scroll = useRef<HTMLDivElement>(null)
  const [availableWidth, setAvailableWidth] = useState(900)
  useEffect(() => {
    if (!scroll.current) return
    const observer = new ResizeObserver(entries => setAvailableWidth(entries[0].contentRect.width - 24))
    observer.observe(scroll.current)
    return () => observer.disconnect()
  }, [])
  const graph = useMemo(() => project(state, availableWidth), [state, availableWidth])
  const reports = new Set(state.reports.map(report => report.id))
  const affected = new Set(state.impact.affected_artifacts.map(artifact => artifact.id))
  const changed = new Set(state.impact.changed_source_ids)
  const hasChange = !!state.impact.change
  const pending = state.reports.some(report => report.state !== 'current') || state.graph.nodes.some(node => node.current_head && node.kind === 'artifact' && node.state !== 'current')
  return <section className="graph-panel panel" aria-labelledby="graph-title">
    <div className="graph-heading"><div><h2 id="graph-title">Evidence, connected</h2><p>Inputs actually consumed by your tools</p></div><span className="graph-live"><i />HydraDB</span></div>
    <div ref={scroll} className="graph-scroll" tabIndex={0} aria-label="Execution dependency graph. Scroll horizontally on small screens to explore every calculation.">
      <div className="graph-canvas" style={{ width: graph.width, height: graph.height }}>
        <div className="graph-column-label" style={{ left: 18 }}>Sources</div><div className="graph-column-label" style={{ left: 18 + graph.nodeW + graph.gap }}>Calculations</div><div className="graph-column-label" style={{ left: 18 + graph.maxRank * (graph.nodeW + graph.gap) }}>Reports</div>
        <svg className="graph-lines" width={graph.width} height={graph.height} aria-hidden="true"><defs>
          <marker id="arrow-normal" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1 L7 4 L1 7" fill="none" stroke="currentColor" strokeWidth="1.5" /></marker>
          <marker id="arrow-affected" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1 L7 4 L1 7" fill="none" stroke="#bd790b" strokeWidth="1.5" /></marker>
        </defs>{graph.edges.map((edge, index) => {
          const a = graph.positions.get(edge.source), b = graph.positions.get(edge.target)
          if (!a || !b) return null
          const emphasized = (affected.has(edge.source) || changed.has(edge.source)) && affected.has(edge.target)
          const x1 = a.x + graph.nodeW, x2 = b.x, y1 = a.y + 25, y2 = b.y + 25
          const midpoint = x1 + (x2 - x1) / 2
          const source = graph.nodes.find(node => node.id === edge.source)
          const longEdge = x2 - x1 > graph.nodeW
          const bottomLane = source?.logical_id.includes('support') || source?.logical_id.includes('tickets')
          const lane = bottomLane ? graph.height - 14 - index % 2 * 7 : 30 + index % 2 * 7
          // Long dependencies travel in clear lanes rather than disappearing
          // behind intervening nodes and visually implying a false edge.
          const path = longEdge
            ? `M${x1} ${y1} H${x1 + 8} V${lane} H${x2 - 9} V${y2} H${x2 - 3}`
            : `M${x1} ${y1} C${midpoint} ${y1},${midpoint} ${y2},${x2 - 3} ${y2}`
          return <path key={`${edge.source}-${edge.target}-${index}`} d={path} className={emphasized ? 'edge-affected' : 'edge-normal'} markerEnd={`url(#arrow-${emphasized ? 'affected' : 'normal'})`} />
        })}</svg>
        {graph.nodes.map(node => {
          const position = graph.positions.get(node.id)!
          const stale = affected.has(node.id) || changed.has(node.id)
          return <button key={node.id} className={`graph-node ${stale ? 'graph-node-affected' : ''} ${reports.has(node.id) ? 'graph-node-report' : ''}`} style={{ left: position.x, top: position.y, width: graph.nodeW }} onClick={() => onInspect(node.id)} title={`${node.label} · ${node.state}`}>
            <NodeIcon node={node} reportIds={reports} /><span>{displayLabel(node)}</span>
          </button>
        })}
        {!graph.nodes.length && <p className="graph-empty">No complete execution relationships are available.</p>}
      </div>
    </div>
    <div className="graph-foot"><span><MousePointer2 size={13} /><span className="mobile-graph-hint">Scroll to explore · </span>Select a node to inspect its evidence</span><span>{hasChange ? pending ? `${affected.size} affected artifacts` : state.last_refresh ? `${state.last_refresh.executed_artifact_ids.length} artifacts revalidated` : 'Refreshed evidence is current' : 'Receipt-derived dependencies'}</span></div>
  </section>
}
