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

  const [pan,       setPan]       = useState({ x: 60, y: 0 })
  const [zoom,      setZoom]      = useState(1)
  const [dragging,  setDragging]  = useState(false)
  const [svgSize,   setSvgSize]   = useState({ w: 0, h: 0 })
  const dragOrigin    = useRef(null)
  const dragMoved     = useRef(false)
  const scrollGeomRef = useRef({})

  const nodes = pipeline?.nodes ?? []
  const edges = pipeline?.edges ?? []

  const positions = useMemo(() => layoutDAG(nodes, edges), [nodes, edges])

  // Content bounding box (world coords) for scrollbar geometry
  const contentBounds = useMemo(() => {
    const pts = Object.values(positions)
    if (!pts.length) return { minX: 0, maxX: 800 }
    return {
      minX: Math.min(...pts.map(p => p.x)) - 80,
      maxX: Math.max(...pts.map(p => p.x)) + NODE_W + 80,
    }
  }, [positions])

  // Track SVG viewport size for scrollbar
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const update = () => {
      const r = el.getBoundingClientRect()
      setSvgSize({ w: r.width, h: r.height })
    }
    update()
    const obs = new ResizeObserver(update)
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Build a lookup: job_id → node object
  const nodeById = useMemo(() => {
    const map = {}
    nodes.forEach(n => { map[n.id] = n })
    return map
  }, [nodes])

  // Direct I/O from pre-computed fields on the selected node
  const activeId = selectedId
  const { directParents, directChildren, lineageSet } = useMemo(() => {
    if (!activeId) return { directParents: new Set(), directChildren: new Set(), lineageSet: new Set() }
    const node = nodeById[activeId]
    const directParents  = new Set(node?.inputs  ?? [])
    const directChildren = new Set(node?.outputs ?? [])
    const lineageSet     = new Set([activeId, ...directParents, ...directChildren])
    return { directParents, directChildren, lineageSet }
  }, [activeId, nodeById])

  const isActive = activeId !== null

  // Horizontal scrollbar geometry
  const TRACK_PAD      = 16
  const contentW       = contentBounds.maxX - contentBounds.minX
  const viewW          = svgSize.w / zoom
  const scrollRatio    = svgSize.w > 0 ? Math.min(1, viewW / contentW) : 1
  const trackW         = Math.max(0, svgSize.w - TRACK_PAD * 2)
  const thumbW         = Math.max(32, scrollRatio * trackW)
  const trackUsable    = trackW - thumbW
  const worldLeft      = -pan.x / zoom
  const scrollableWorld = Math.max(0, contentW - viewW)
  const scrollPct      = scrollableWorld > 0
    ? Math.max(0, Math.min(1, (worldLeft - contentBounds.minX) / scrollableWorld))
    : 0
  const thumbLeft = TRACK_PAD + scrollPct * trackUsable

  scrollGeomRef.current = { thumbW, trackUsable, scrollableWorld, contentBounds, zoom }

  const onScrollbarMouseDown = useCallback(e => {
    e.preventDefault()
    e.stopPropagation()
    const startClientX  = e.clientX
    const startPanX     = pan.x
    const { trackUsable, scrollableWorld, contentBounds, zoom } = scrollGeomRef.current
    if (trackUsable <= 0 || scrollableWorld <= 0) return
    const startWorldLeft = -startPanX / zoom

    const onMove = mv => {
      const delta       = mv.clientX - startClientX
      const worldDelta  = (delta / trackUsable) * scrollableWorld
      const newWorldLeft = Math.max(
        contentBounds.minX,
        Math.min(contentBounds.minX + scrollableWorld, startWorldLeft + worldDelta)
      )
      setPan(p => ({ ...p, x: -newWorldLeft * zoom }))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [pan.x])

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
    dragMoved.current = false
    if (e.target.closest('[data-node]')) return
    setDragging(true)
    dragOrigin.current = { ox: pan.x, oy: pan.y, mx: e.clientX, my: e.clientY }
  }, [pan])

  const onMouseMove = useCallback(e => {
    if (!dragging || !dragOrigin.current) return
    dragMoved.current = true
    const { ox, oy, mx, my } = dragOrigin.current
    setPan({ x: ox + e.clientX - mx, y: oy + e.clientY - my })
  }, [dragging])

  const onMouseUp = useCallback(() => setDragging(false), [])

  // Click on empty canvas → deselect
  const onSvgClick = useCallback(e => {
    if (dragMoved.current) return
    if (e.target.closest('[data-node]')) return
    onSelect(null)
  }, [onSelect])

  // Zoom handler (non-passive so we can preventDefault)
  const onWheel = useCallback(e => {
    e.preventDefault()
    setZoom(z => Math.max(0.25, Math.min(2, z * (e.deltaY < 0 ? 1.1 : 0.9))))
  }, [])

  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [onWheel, pipeline])

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

    {/* Lineage legend — visible only when a node is active */}
    {isActive && (
      <div style={{
        position: 'absolute', top: 12, left: 12, zIndex: 10,
        display: 'flex', gap: 12, alignItems: 'center',
        background: theme.surface, border: `1px solid ${theme.border}`,
        borderRadius: 6, padding: '4px 10px', fontSize: 11, color: theme.textMuted,
        pointerEvents: 'none',
      }}>
        <span><span style={{ color: '#6366f1', fontWeight: 700 }}>—</span> inputs</span>
        <span><span style={{ color: theme.accent, fontWeight: 700 }}>—</span> selected</span>
        <span><span style={{ color: '#10b981', fontWeight: 700 }}>—</span> outputs</span>
      </div>
    )}

    {/* Zoom controls */}
    <div style={{ position: 'absolute', bottom: 16, right: 16, zIndex: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={btnStyle} onClick={() => setZoom(z => Math.min(2, z * 1.25))}>+</div>
      <div style={{ ...btnStyle, fontSize: 10, fontFamily: 'monospace' }}>{Math.round(zoom * 100)}%</div>
      <div style={btnStyle} onClick={() => setZoom(z => Math.max(0.25, z * 0.8))}>−</div>
    </div>

    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%', cursor: dragging ? 'grabbing' : 'grab', background: theme.bg }}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onClick={onSvgClick}
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
          const key      = `${e.source}→${e.target}`
          const isInput  = isActive && e.target === activeId
          const isOutput = isActive && e.source === activeId
          const edgeColor = isInput ? '#6366f1' : isOutput ? '#10b981' : theme.border2
          const edgeActive = isInput || isOutput
          return (
            <path
              key={key}
              d={`M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`}
              fill="none"
              stroke={edgeColor}
              strokeWidth={edgeActive ? 2 : 1}
              strokeOpacity={isActive ? (edgeActive ? 1 : 0.06) : 0.35}
            />
          )
        })}

        {/* ── Nodes ── */}
        {nodes.map(node => {
          const pos = positions[node.id]
          if (!pos) return null
          const typeColor    = TYPE_COLOR[node.type]    ?? theme.textMuted
          const statusColor  = STATUS_COLOR[node.status] ?? theme.textMuted
          const selected     = selectedId === node.id
          const inLineage      = !isActive || lineageSet.has(node.id)
          const isDirectParent = isActive && directParents.has(node.id)
          const isDirectChild  = isActive && directChildren.has(node.id)

          return (
            <g
              key={node.id}
              data-node="1"
              transform={`translate(${pos.x},${pos.y})`}
              onClick={e => { e.stopPropagation(); onSelect(node.id === selectedId ? null : node.id) }}
              style={{ cursor: 'pointer', opacity: inLineage ? 1 : 0.2, transition: 'opacity 0.15s' }}
            >
              {/* Direct parent ring (indigo = input) */}
              {isDirectParent && (
                <rect x={-3} y={-3} width={NODE_W + 6} height={NODE_H + 6} rx={9}
                  fill="none" stroke="#6366f1" strokeWidth={1.5} />
              )}

              {/* Direct child ring (green = output) */}
              {isDirectChild && (
                <rect x={-3} y={-3} width={NODE_W + 6} height={NODE_H + 6} rx={9}
                  fill="none" stroke="#10b981" strokeWidth={1.5} />
              )}

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

              {/* Resolution right-aligned on same row as type label */}
              {node.resolution != null && (
                <text x={NODE_W - 20} y={34} fontSize={9} fontFamily="monospace"
                      fill={theme.textMuted} textAnchor="end">
                  {node.resolution.toFixed(1)} Å
                </text>
              )}
            </g>
          )
        })}
      </g>
    </svg>

    {/* Horizontal scrollbar */}
    {scrollRatio < 0.99 && (
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 12, pointerEvents: 'none' }}>
        {/* Track */}
        <div style={{
          position: 'absolute', left: TRACK_PAD, right: TRACK_PAD,
          top: 4, height: 4,
          background: theme.border, borderRadius: 2,
        }} />
        {/* Thumb */}
        <div
          onMouseDown={onScrollbarMouseDown}
          style={{
            position: 'absolute', top: 3, height: 6,
            left: thumbLeft, width: thumbW,
            background: theme.textMuted, borderRadius: 3,
            cursor: 'pointer', pointerEvents: 'auto',
          }}
        />
      </div>
    )}
    </div>
  )
}
