import React, { useRef, useState, useEffect, useCallback, useMemo } from 'react'
import { useTheme, TYPE_COLOR, STATUS_COLOR } from '../theme.js'

const NODE_W = 164
const NODE_H = 50
const COL_W  = 220   // horizontal center-to-center
const ROW_H  = 74    // vertical center-to-center

function layoutDAG(nodes, edges) {
  if (!nodes.length) return {}

  const childMap = {}
  const parentMap = {}
  nodes.forEach(n => { childMap[n.id] = []; parentMap[n.id] = [] })
  edges.forEach(e => {
    childMap[e.source]?.push(e.target)
    parentMap[e.target]?.push(e.source)
  })

  // Longest-path column assignment (handles DAGs correctly)
  const col = {}
  const inProgress = new Set()

  function assignCol(id) {
    if (id in col) return col[id]
    if (inProgress.has(id)) { col[id] = 0; return 0 }   // cycle guard
    inProgress.add(id)
    const parents = parentMap[id] ?? []
    col[id] = parents.length === 0
      ? 0
      : Math.max(...parents.map(p => assignCol(p))) + 1
    inProgress.delete(id)
    return col[id]
  }
  nodes.forEach(n => assignCol(n.id))

  // Group by column, then assign centered row positions
  const byCol = {}
  nodes.forEach(n => {
    const c = col[n.id] ?? 0
    ;(byCol[c] ??= []).push(n.id)
  })

  const positions = {}
  Object.entries(byCol).forEach(([c, ids]) => {
    const offset = ((ids.length - 1) * ROW_H) / 2
    ids.forEach((id, i) => {
      positions[id] = { x: Number(c) * COL_W, y: i * ROW_H - offset }
    })
  })
  return positions
}

export default function DAGCanvas({ pipeline, selectedId, onSelect }) {
  const theme    = useTheme()
  const svgRef   = useRef(null)
  const centered = useRef(false)

  const [pan,      setPan]      = useState({ x: 60, y: 0 })
  const [zoom,     setZoom]     = useState(1)
  const [dragging, setDragging] = useState(false)
  const dragOrigin = useRef(null)

  const nodes = pipeline?.nodes ?? []
  const edges = pipeline?.edges ?? []

  const positions = useMemo(() => layoutDAG(nodes, edges), [nodes, edges])

  // On first load: zoom=1, pan so column-0 nodes are visible near the left edge, centered vertically
  useEffect(() => {
    if (centered.current || !Object.keys(positions).length || !svgRef.current) return
    centered.current = true
    const pts = Object.values(positions)
    const minX = Math.min(...pts.map(p => p.x))
    const minY = Math.min(...pts.map(p => p.y))
    const maxY = Math.max(...pts.map(p => p.y))
    const { height } = svgRef.current.getBoundingClientRect()
    setZoom(1)
    setPan({
      x: 48 - minX,
      y: height / 2 - (minY + (maxY - minY) / 2 + NODE_H / 2),
    })
  }, [positions])

  // Pan handlers
  const onMouseDown = useCallback(e => {
    if (e.target.closest('[data-node]')) return
    setDragging(true)
    dragOrigin.current = { ox: pan.x, oy: pan.y, mx: e.clientX, my: e.clientY }
  }, [pan])

  const onMouseMove = useCallback(e => {
    if (!dragging || !dragOrigin.current) return
    const { ox, oy, mx, my } = dragOrigin.current
    setPan({ x: ox + e.clientX - mx, y: oy + e.clientY - my })
  }, [dragging])

  const onMouseUp = useCallback(() => setDragging(false), [])

  // Zoom handler (non-passive so we can preventDefault)
  const onWheel = useCallback(e => {
    e.preventDefault()
    setZoom(z => Math.max(0.15, Math.min(3, z * (e.deltaY < 0 ? 1.1 : 0.9))))
  }, [])

  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [onWheel])

  // Edges connected to selected node (for highlighting)
  const highlighted = useMemo(() => {
    if (!selectedId) return new Set()
    return new Set(
      edges
        .filter(e => e.source === selectedId || e.target === selectedId)
        .map(e => `${e.source}→${e.target}`)
    )
  }, [selectedId, edges])

  if (!pipeline) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: theme.textMuted, fontSize: 14 }}>
        Loading pipeline…
      </div>
    )
  }

  const btnStyle = {
    width: 28, height: 28,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: theme.surface, border: `1px solid ${theme.border}`,
    color: theme.text, borderRadius: 6, cursor: 'pointer', fontSize: 16, userSelect: 'none',
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
    {/* Zoom controls */}
    <div style={{ position: 'absolute', bottom: 16, right: 16, zIndex: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={btnStyle} onClick={() => setZoom(z => Math.min(3, z * 1.25))}>+</div>
      <div style={{ ...btnStyle, fontSize: 10, fontFamily: 'monospace' }}>{Math.round(zoom * 100)}%</div>
      <div style={btnStyle} onClick={() => setZoom(z => Math.max(0.15, z * 0.8))}>−</div>
    </div>
    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%', cursor: dragging ? 'grabbing' : 'grab', background: theme.bg }}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>

        {/* ── Edges ── */}
        {edges.map(e => {
          const s = positions[e.source]
          const t = positions[e.target]
          if (!s || !t) return null
          const x1 = s.x + NODE_W, y1 = s.y + NODE_H / 2
          const x2 = t.x,         y2 = t.y + NODE_H / 2
          const cx = (x1 + x2) / 2
          const key = `${e.source}→${e.target}`
          const hot = highlighted.has(key)
          return (
            <path
              key={key}
              d={`M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`}
              fill="none"
              stroke={hot ? theme.accent : theme.border2}
              strokeWidth={hot ? 2 : 1}
              strokeOpacity={hot ? 1 : 0.35}
            />
          )
        })}

        {/* ── Nodes ── */}
        {nodes.map(node => {
          const pos = positions[node.id]
          if (!pos) return null
          const typeColor   = TYPE_COLOR[node.type]   ?? theme.textMuted
          const statusColor = STATUS_COLOR[node.status] ?? theme.textMuted
          const selected    = selectedId === node.id

          return (
            <g
              key={node.id}
              data-node="1"
              transform={`translate(${pos.x},${pos.y})`}
              onClick={() => onSelect(node.id)}
              style={{ cursor: 'pointer' }}
            >
              {/* Selection ring */}
              {selected && (
                <rect x={-3} y={-3} width={NODE_W + 6} height={NODE_H + 6} rx={9}
                  fill="none" stroke={theme.accent} strokeWidth={2} />
              )}

              {/* Node body */}
              <rect width={NODE_W} height={NODE_H} rx={6}
                fill={theme.surface} stroke={theme.border} strokeWidth={1} />

              {/* Left type-color accent bar */}
              <rect width={4} height={NODE_H} rx={2} fill={typeColor} />

              {/* Status dot */}
              <circle cx={NODE_W - 12} cy={NODE_H / 2} r={4} fill={statusColor} />

              {/* Job number */}
              <text x={12} y={19} fontSize={11} fontFamily="monospace" fill={theme.text}>
                {node.id.split('/').pop()}
              </text>

              {/* Type label */}
              <text x={12} y={34} fontSize={10} fontFamily="sans-serif" fill={typeColor}>
                {node.type}
              </text>
            </g>
          )
        })}
      </g>
    </svg>
    </div>
  )
}
