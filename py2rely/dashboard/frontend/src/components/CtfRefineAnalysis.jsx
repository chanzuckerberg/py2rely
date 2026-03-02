import React from 'react'
import { useTheme } from '../theme.js'
import {
  ResponsiveContainer, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip,
  BarChart, Bar,
} from 'recharts'

export default function CtfRefineAnalysis({ data }) {
  const T = useTheme()

  const panelStyle = {
    background: T.surface2, borderRadius: 8, padding: 12,
    border: `1px solid ${T.border}`, flex: '1 1 240px', minWidth: 0,
  }
  const titleStyle   = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 8 }
  const axisProps    = { tick: { fontSize: 10, fill: T.textMuted }, stroke: T.border }
  const gridProps    = { strokeDasharray: '3 3', stroke: T.border }
  const tooltipStyle = {
    contentStyle: { background: T.surface, border: `1px solid ${T.border}`, fontSize: 10, borderRadius: 4 },
  }

  if (!data.per_tomo?.length) {
    return (
      <div style={{ padding: 16, color: T.textMuted, fontSize: 12 }}>
        No refined defocus data found in temp/defocus/.
      </div>
    )
  }

  const { per_tomo, n_tomograms, n_tilts_total } = data

  // Histogram of mean defocus
  const defValues = per_tomo.map(t => t.defocusU)
  const minD = Math.min(...defValues), maxD = Math.max(...defValues)
  const nBins = 20
  const binW  = (maxD - minD) / nBins || 1
  const histBins = Array.from({ length: nBins }, (_, i) => ({
    bin_center: parseFloat((minD + (i + 0.5) * binW).toFixed(3)),
    count: 0,
  }))
  defValues.forEach(v => {
    const i = Math.min(nBins - 1, Math.floor((v - minD) / binW))
    histBins[i].count++
  })

  return (
    <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>

        {/* Summary */}
        <div style={{ ...panelStyle, flex: '0 0 auto' }}>
          <div style={titleStyle}>Summary</div>
          <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
            <tbody>
              {[
                ['Tomograms refined', n_tomograms],
                ['Total tilts',       n_tilts_total],
                ['Mean defocus',      `${(defValues.reduce((a, b) => a + b, 0) / defValues.length).toFixed(2)} μm`],
                ['Defocus range',     `${minD.toFixed(2)} – ${maxD.toFixed(2)} μm`],
              ].map(([label, value]) => (
                <tr key={label} style={{ borderBottom: `1px solid ${T.border}` }}>
                  <td style={{ padding: '5px 12px 5px 0', color: T.textMuted, whiteSpace: 'nowrap' }}>{label}</td>
                  <td style={{ padding: '5px 0', color: T.text, fontFamily: 'monospace' }}>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Defocus U vs V scatter */}
        <div style={panelStyle}>
          <div style={titleStyle}>Defocus U vs V per Tomogram (μm)</div>
          <ResponsiveContainer width="100%" height={200}>
            <ScatterChart margin={{ top: 4, right: 8, bottom: 16, left: 4 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="defocusU" type="number" name="Defocus U" {...axisProps}
                label={{ value: 'Defocus U (μm)', position: 'insideBottom', offset: -8, style: { fontSize: 10, fill: T.textMuted } }}
                tickFormatter={v => Number(v).toFixed(1)}
              />
              <YAxis dataKey="defocusV" type="number" name="Defocus V" {...axisProps}
                tickFormatter={v => Number(v).toFixed(1)}
              />
              <Tooltip
                {...tooltipStyle}
                cursor={{ strokeDasharray: '3 3' }}
                content={({ payload }) => {
                  if (!payload?.length) return null
                  const d = payload[0]?.payload
                  return (
                    <div style={{ background: T.surface, border: `1px solid ${T.border}`, padding: '4px 8px', fontSize: 10, borderRadius: 4 }}>
                      <div style={{ color: T.textMuted }}>{d?.name}</div>
                      <div>U: {d?.defocusU?.toFixed(3)} μm</div>
                      <div>V: {d?.defocusV?.toFixed(3)} μm</div>
                      <div>Astig: {d?.astigmatism?.toFixed(3)} μm</div>
                    </div>
                  )
                }}
              />
              <Scatter data={per_tomo} fill={T.accent} opacity={0.7} r={3} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* Defocus distribution histogram */}
        <div style={panelStyle}>
          <div style={titleStyle}>Mean Defocus Distribution (μm)</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={histBins} margin={{ top: 4, right: 8, bottom: 20, left: 4 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="bin_center" {...axisProps}
                tickFormatter={v => Number(v).toFixed(1)}
                label={{ value: 'Defocus (μm)', position: 'insideBottom', offset: -10, style: { fontSize: 10, fill: T.textMuted } }}
              />
              <YAxis {...axisProps}
                label={{ value: 'Tomos', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: T.textMuted } }}
              />
              <Tooltip
                {...tooltipStyle}
                formatter={(v) => [v, 'Tomograms']}
                labelFormatter={v => `~${Number(v).toFixed(2)} μm`}
              />
              <Bar dataKey="count" fill={T.accent} opacity={0.85} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  )
}
