import React, { useState, useRef, useEffect } from 'react'
import { useTheme } from '../theme.js'
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import { AngularDistHeatmap } from './Class3DAnalysis.jsx'

function SummaryBox({ summary, T }) {
  if (!summary || !Object.keys(summary).length) return null

  const rows = [
    { label: 'Final resolution',  value: summary.final_resolution != null ? `${summary.final_resolution} Å` : '—' },
    { label: 'Nyquist',           value: summary.nyquist           != null ? `${summary.nyquist} Å`           : '—' },
    { label: 'Pixel size',        value: summary.pixel_size        != null ? `${summary.pixel_size} Å/px`     : '—' },
    { label: 'Box size',          value: summary.box_size          ? `${summary.box_size} px`                 : '—' },
    { label: 'Iterations',        value: summary.iterations        != null ? summary.iterations                : '—' },
    { label: 'Acc. rotations',    value: summary.acc_rot           != null ? `${summary.acc_rot}°`            : '—' },
    { label: 'Acc. translations', value: summary.acc_trans         != null ? `${summary.acc_trans} Å`         : '—' },
    { label: 'Avg. pMax',         value: summary.avg_pmax          != null ? summary.avg_pmax                 : '—' },
  ]

  return (
    <div style={{
      background: T.surface2, borderRadius: 8, padding: 12,
      border: `1px solid ${T.border}`, flex: '0 0 auto',
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 8 }}>Summary</div>
      <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
        <tbody>
          {rows.map(({ label, value }) => (
            <tr key={label} style={{ borderBottom: `1px solid ${T.border}` }}>
              <td style={{ padding: '5px 12px 5px 0', color: T.textMuted, whiteSpace: 'nowrap' }}>{label}</td>
              <td style={{ padding: '5px 0', color: T.text, fontFamily: 'monospace' }}>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Refine3DAnalysis({ data }) {
  const T = useTheme()

  const panelStyle = {
    background: T.surface2, borderRadius: 8, padding: 12,
    border: `1px solid ${T.border}`, flex: '1 1 260px', minWidth: 0,
  }
  const titleStyle = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 8 }

  const axisProps = { tick: { fontSize: 10, fill: T.textMuted }, stroke: T.border }
  const gridProps = { strokeDasharray: '3 3', stroke: T.border }
  const tooltipStyle = {
    contentStyle: { background: T.surface, border: `1px solid ${T.border}`, fontSize: 11, borderRadius: 4 },
    labelStyle: { color: T.textMuted },
  }

  const nyquist = data.fsc?.length ? Math.min(...data.fsc.map(d => d.resolution_a)) : 1
  const [maxA, setMaxA] = useState(100)
  const chartRef = useRef(null)
  useEffect(() => {
    const onWheel = e => {
      const el = chartRef.current
      if (!el) return
      const { left, right, top, bottom } = el.getBoundingClientRect()
      if (e.clientX < left || e.clientX > right || e.clientY < top || e.clientY > bottom) return
      e.preventDefault()
      setMaxA(prev => Math.max(5, Math.min(100, prev * (e.deltaY < 0 ? 0.9 : 1.1))))
    }
    document.addEventListener('wheel', onWheel, { passive: false })
    return () => document.removeEventListener('wheel', onWheel)
  }, [])

  if (!data.convergence?.length && !data.fsc?.length) {
    return (
      <div style={{ padding: 16, color: T.textMuted, fontSize: 12 }}>
        No convergence data found. Job may still be in progress.
      </div>
    )
  }

  return (
    <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Row 1: Summary + Resolution Convergence */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <SummaryBox summary={data.summary} T={T} />

          {data.convergence?.length > 0 && (
            <div style={panelStyle}>
              <div style={titleStyle}>Resolution Convergence</div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={data.convergence} margin={{ top: 4, right: 8, bottom: 16, left: 4 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="iter" {...axisProps}
                    label={{ value: 'Iteration', position: 'insideBottom', offset: -8, style: { fontSize: 10, fill: T.textMuted } }}
                  />
                  <YAxis
                    {...axisProps}
                    label={{ value: 'Å', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: T.textMuted } }}
                  />
                  <Tooltip
                    {...tooltipStyle}
                    formatter={v => [`${Number(v).toFixed(2)} Å`, 'Resolution']}
                  />
                  <Line type="monotone" dataKey="resolution" stroke={T.accent} dot={{ r: 3, fill: T.accent }} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Row 2: Gold-Standard FSC + Angular Distribution */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {data.fsc?.length > 0 && (
            <div style={panelStyle} ref={chartRef}>
              <div style={{ ...titleStyle, display: 'flex', alignItems: 'center' }}>
                <span>Gold-Standard FSC</span>
                {maxA !== 100 && (
                  <button onClick={() => setMaxA(100)} style={{ marginLeft: 'auto', fontSize: 9, padding: '1px 6px', borderRadius: 3, cursor: 'pointer', background: 'none', border: `1px solid ${T.border}`, color: T.textMuted }}>
                    Reset zoom
                  </button>
                )}
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={data.fsc} margin={{ top: 4, right: 8, bottom: 16, left: 4 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="resolution_a"
                    reversed type="number"
                    domain={[nyquist, maxA]}
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
                    formatter={v => [Number(v).toFixed(3), 'FSC']}
                    labelFormatter={v => `${v} Å`}
                  />
                  <Line type="monotone" dataKey="fsc" stroke={T.accent} dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {data.angular_dist && (
            <div style={{ background: T.surface2, borderRadius: 8, padding: 12, border: `1px solid ${T.border}`, flex: '0 0 auto' }}>
              <div style={titleStyle}>Angular Distribution (Rot × Tilt)</div>
              <AngularDistHeatmap grid={data.angular_dist} />
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
