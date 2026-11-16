import type { CSSProperties } from 'react'

/** The six hosted connector tools, from README.md ("The hosted connector exposes six tools"). */
export const CONNECTOR_TOOLS = [
  'create_csv_reports',
  'inspect_reports',
  'inspect_evidence',
  'update_csv',
  'refresh_reports',
  'export_current_reports',
] as const

const W = 360
const H = 225
const AGENT = { x: 22, y: H / 2 - 20, w: 92, h: 40 }
const PILL = { x: 158, w: 182, h: 25, gap: 8.6 }
const top0 = (H - (CONNECTOR_TOOLS.length * PILL.h + (CONNECTOR_TOOLS.length - 1) * PILL.gap)) / 2

/**
 * An agent node threaded to the connector's tools. Each time `run` flips between 'a' and 'b' (in view, then hover or focus), a pulse
 * travels down each thread in turn and the tool it reaches lights up: the agent calling its tools.
 */
export default function AgentThreads({ run }: { run: 'idle' | 'a' | 'b' }) {
  const sx = AGENT.x + AGENT.w
  const sy = H / 2
  return (
    <svg className="try-agent-viz" data-run={run} viewBox={`0 0 ${W} ${H}`} aria-hidden focusable="false"
      >
      {CONNECTOR_TOOLS.map((tool, i) => {
        const y = top0 + i * (PILL.h + PILL.gap) + PILL.h / 2
        const mx = (sx + PILL.x) / 2
        const d = `M${sx} ${sy} C${mx} ${sy} ${mx} ${y} ${PILL.x} ${y}`
        const delay = { '--i': i } as CSSProperties
        return (
          <g key={tool} className="try-tool" style={delay}>
            <path d={d} className="try-tool-thread" />
            <path d={d} pathLength={100} className="try-tool-pulse" />
            <rect x={PILL.x} y={y - PILL.h / 2} width={PILL.w} height={PILL.h} rx={PILL.h / 2} className="try-tool-pill" />
            <circle cx={PILL.x + 13} cy={y} r={2.6} className="try-tool-dot" />
            <text x={PILL.x + 23} y={y} className="try-tool-name" dominantBaseline="central">{tool}</text>
          </g>
        )
      })}
      <rect x={AGENT.x} y={AGENT.y} width={AGENT.w} height={AGENT.h} rx={10} className="try-agent-node" />
      <circle cx={sx} cy={sy} r={3.4} className="try-agent-port" />
      <text x={AGENT.x + AGENT.w / 2} y={sy} className="try-agent-name" textAnchor="middle" dominantBaseline="central">your agent</text>
    </svg>
  )
}
