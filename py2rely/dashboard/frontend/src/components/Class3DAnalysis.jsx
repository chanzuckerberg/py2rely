import React, { useState, useRef, useEffect } from 'react'
import { useTheme } from '../theme.js'
import {
  ResponsiveContainer, AreaChart, Area,
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts'

// Class color palette
const CLASS_COLORS = ['#a78bfa', '#06b6d4', '#f59e0b', '#10b981', '#f43f5e', '#3b82f6', '#8b5cf6', '#ec4899']

function classColor(i) {
  return CLASS_COLORS[i % CLASS_COLORS.length]
}

// Angular distribution heatmap using SVG
function AngularDistHeatmap({ grid }) {
  const T = useTheme()
  if (!grid) return (
    <div style={{ fontSize: 11, color: T.textMuted, padding: 8 }}>
      Angular distribution data unavailable.
    </div>
  )

  const nRot  = grid.length        // 36
  const nTilt = grid[0]?.length ?? 0  // 18
  const cellW = 8
  const cellH = 8
  const padL  = 24
  const padB  = 18
  const svgW  = nRot * cellW + padL + 4
  const svgH  = nTilt * cellH + padB + 4

  // Compute max for color scale
  let maxCount = 1
  for (const row of grid) for (const v of row) if (v > maxCount) maxCount = v

  // Parse accent hex to RGB for opacity scale
  const accent = T.accent  // e.g. '#a78bfa'

  return (
    <svg width={svgW} height={svgH} style={{ display: 'block' }}>
      {/* Cells */}
      {grid.map((rotBin, ri) =>
        rotBin.map((count, ti) => (
          <rect
            key={`${ri}-${ti}`}
            x={padL + ri * cellW}
            y={ti * cellH}
            width={cellW - 0.5}
            height={cellH - 0.5}
            fill={accent}
            opacity={maxCount > 0 ? count / maxCount : 0}
          />
        ))
      )}
      {/* Rot axis labels (every 90°) */}
      {[0, 9, 18, 27].map(i => (
        <text key={i} x={padL + i * cellW + cellW / 2} y={nTilt * cellH + padB - 4}
          textAnchor="middle" fontSize={9} fill={T.textMuted}
        >
          {i * 10}°
        </text>
      ))}
      <text x={padL + nRot * cellW / 2} y={nTilt * cellH + padB + 2}
        textAnchor="middle" fontSize={9} fill={T.textMuted}
      >
        Rot
      </text>
      {/* Tilt axis labels (every 45°) */}
      {[0, 4, 9, 13, 18].map(ti => (
        <text key={ti} x={padL - 3} y={ti * cellH + cellH / 2 + 3}
          textAnchor="end" fontSize={9} fill={T.textMuted}
        >
          {ti * 10}°
        </text>
      ))}
      <text
        x={8} y={nTilt * cellH / 2}
        textAnchor="middle" fontSize={9} fill={T.textMuted}
        transform={`rotate(-90, 8, ${nTilt * cellH / 2})`}
      >
        Tilt
      </text>
    </svg>
  )
}

export default function Class3DAnalysis({ data }) {
  const T = useTheme()
  const [hiddenClasses, setHiddenClasses] = useState(new Set())

  const nClasses = data.class_stats?.length ?? 0

  // Build convergence data for recharts AreaChart
  // [{ iter, class_1: pct, class_2: pct, ... }, ...]
  const convergenceData = (data.convergence ?? []).map(d => {
    const obj = { iter: d.iter }
    ;(d.class_dist ?? []).forEach((v, i) => {
      obj[`class_${i + 1}`] = parseFloat((v * 100).toFixed(1))
    })
    return obj
  })

  // Build FSC data merged across classes
  // All classes share the same spectral shells — merge by index
  const fscKeys  = Object.keys(data.fsc_per_class ?? {})
  const fscData  = fscKeys.length > 0
    ? (data.fsc_per_class[fscKeys[0]] ?? []).map((row, idx) => {
        const obj = { resolution_a: row.resolution_a }
        fscKeys.forEach(cls => {
          obj[`class_${cls}`] = data.fsc_per_class[cls]?.[idx]?.fsc
        })
        return obj
      })
    : []

  const toggleClass = (i) => {
    setHiddenClasses(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const fscNyquist = fscData.length ? Math.min(...fscData.map(d => d.resolution_a)) : 1
  const [fscMaxA, setFscMaxA] = useState(100)
  const fscChartRef = useRef(null)
  useEffect(() => {
    const onWheel = e => {
      const el = fscChartRef.current
      if (!el) return
      const { left, right, top, bottom } = el.getBoundingClientRect()
      if (e.clientX < left || e.clientX > right || e.clientY < top || e.clientY > bottom) return
      e.preventDefault()
      setFscMaxA(prev => Math.max(5, Math.min(100, prev * (e.deltaY < 0 ? 0.9 : 1.1))))
    }
    document.addEventListener('wheel', onWheel, { passive: false })
    return () => document.removeEventListener('wheel', onWheel)
  }, [])

  const panelStyle = {
    background: T.surface2, borderRadius: 8, padding: 12,
    border: `1px solid ${T.border}`,
  }
  const titleStyle = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 8 }
  const axisProps  = { tick: { fontSize: 10, fill: T.textMuted }, stroke: T.border }
  const gridProps  = { strokeDasharray: '3 3', stroke: T.border }
  const tooltipStyle = {
    contentStyle: { background: T.surface, border: `1px solid ${T.border}`, fontSize: 11, borderRadius: 4 },
  }

  return (
    <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Row 1: Convergence + FSC */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>

          {/* Class convergence (stacked area) */}
          {convergenceData.length > 0 && (
            <div style={{ ...panelStyle, flex: '1 1 280px', minWidth: 0 }}>
              <div style={titleStyle}>Class Distribution</div>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={convergenceData} margin={{ top: 4, right: 8, bottom: 16, left: 4 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="iter" {...axisProps}
                    label={{ value: 'Iteration', position: 'insideBottom', offset: -8, style: { fontSize: 10, fill: T.textMuted } }}
                  />
                  <YAxis
                    domain={[0, 100]} {...axisProps}
                    tickFormatter={v => `${v}%`}
                  />
                  <Tooltip
                    {...tooltipStyle}
                    formatter={(v, name) => [`${v}%`, name]}
                  />
                  {Array.from({ length: nClasses }, (_, i) => (
                    <Area
                      key={i}
                      type="monotone"
                      dataKey={`class_${i + 1}`}
                      name={`Class ${i + 1}`}
                      stackId="1"
                      stroke={classColor(i)}
                      fill={classColor(i)}
                      fillOpacity={0.7}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Per-class FSC */}
          {fscData.length > 0 && (() => {
            return (
            <div style={{ ...panelStyle, flex: '1 1 280px', minWidth: 0 }} ref={fscChartRef}>
              <div style={{ ...titleStyle, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span>FSC per Class</span>
                {fscMaxA !== 100 && (
                  <button onClick={() => setFscMaxA(100)} style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, cursor: 'pointer', background: 'none', border: `1px solid ${T.border}`, color: T.textMuted }}>
                    Reset zoom
                  </button>
                )}
                <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
                  {Array.from({ length: nClasses }, (_, i) => (
                    <button
                      key={i}
                      onClick={() => toggleClass(i + 1)}
                      style={{
                        fontSize: 9, padding: '1px 5px', borderRadius: 3, cursor: 'pointer',
                        background: hiddenClasses.has(i + 1) ? T.surface : classColor(i) + '33',
                        border: `1px solid ${classColor(i)}`,
                        color: hiddenClasses.has(i + 1) ? T.textMuted : classColor(i),
                      }}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={fscData} margin={{ top: 4, right: 8, bottom: 16, left: 4 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="resolution_a"
                    reversed type="number"
                    domain={[fscNyquist, fscMaxA]}
                    allowDataOverflow
                    {...axisProps}
                    label={{ value: 'Resolution (Å)', position: 'insideBottom', offset: -8, style: { fontSize: 10, fill: T.textMuted } }}
                  />
                  <YAxis domain={[0, 1]} {...axisProps} />
                  <ReferenceLine y={0.143} stroke="#ef4444" strokeDasharray="4 4"
                    label={{ value: '0.143', fill: '#ef4444', fontSize: 9, position: 'insideTopRight' }}
                  />
                  <Tooltip
                    {...tooltipStyle}
                    formatter={v => [v != null ? Number(v).toFixed(3) : '—']}
                    labelFormatter={v => `${v} Å`}
                  />
                  {Array.from({ length: nClasses }, (_, i) => (
                    <Line
                      key={i}
                      type="monotone"
                      dataKey={`class_${i + 1}`}
                      name={`Class ${i + 1}`}
                      stroke={classColor(i)}
                      dot={false}
                      strokeWidth={1.5}
                      hide={hiddenClasses.has(i + 1)}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            )
          })()}
        </div>

        {/* Row 2: Angular distribution + Stats table */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>

          {/* Angular distribution heatmap */}
          <div style={{ ...panelStyle, flex: '0 0 auto' }}>
            <div style={titleStyle}>Angular Distribution (Rot × Tilt)</div>
            <AngularDistHeatmap grid={data.angular_dist} />
          </div>

          {/* Per-class stats table */}
          {data.class_stats?.length > 0 && (
            <div style={{ ...panelStyle, flex: '1 1 240px', minWidth: 0 }}>
              <div style={titleStyle}>Class Statistics</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr>
                    {['Class', 'Particles (%)', 'Res. (Å)', 'Acc. Rot (°)', 'Acc. Trans (Å)'].map(h => (
                      <th key={h} style={{
                        padding: '4px 6px', textAlign: 'left', fontSize: 10,
                        color: T.textMuted, borderBottom: `1px solid ${T.border}`,
                        fontWeight: 600, whiteSpace: 'nowrap',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.class_stats.map(row => (
                    <tr key={row.class} style={{ borderBottom: `1px solid ${T.border}` }}>
                      <td style={{ padding: '4px 6px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: classColor(row.class - 1), flexShrink: 0 }} />
                          {row.class}
                        </span>
                      </td>
                      <td style={{ padding: '4px 6px', color: T.text }}>{row.distribution?.toFixed(1) ?? '—'}</td>
                      <td style={{ padding: '4px 6px', color: T.text }}>{row.resolution?.toFixed(2) ?? '—'}</td>
                      <td style={{ padding: '4px 6px', color: T.text }}>{row.acc_rot?.toFixed(2) ?? '—'}</td>
                      <td style={{ padding: '4px 6px', color: T.text }}>{row.acc_trans?.toFixed(2) ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
