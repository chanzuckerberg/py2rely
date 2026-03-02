import React from 'react'
import { useTheme } from '../theme.js'
import {
  ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'

export default function PolishAnalysis({ data }) {
  const T = useTheme()

  const panelStyle = {
    background: T.surface2, borderRadius: 8, padding: 12,
    border: `1px solid ${T.border}`,
  }
  const titleStyle = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 8 }

  if (!data.histogram?.length) {
    return (
      <div style={{ padding: 16, color: T.textMuted, fontSize: 12 }}>
        No motion data found in motion.star.
      </div>
    )
  }

  const statItems = [
    { label: 'Particles',     value: data.n_particles },
    { label: 'Median motion', value: `${data.median} Å` },
    { label: 'Mean motion',   value: `${data.mean} Å` },
    { label: 'Max motion',    value: `${data.max} Å` },
  ]

  return (
    <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>

        {/* Summary stats */}
        <div style={{ ...panelStyle, flex: '0 0 auto' }}>
          <div style={titleStyle}>Motion Summary</div>
          <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
            <tbody>
              {statItems.map(({ label, value }) => (
                <tr key={label} style={{ borderBottom: `1px solid ${T.border}` }}>
                  <td style={{ padding: '5px 12px 5px 0', color: T.textMuted, whiteSpace: 'nowrap' }}>{label}</td>
                  <td style={{ padding: '5px 0', color: T.text, fontFamily: 'monospace' }}>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Motion histogram */}
        <div style={{ ...panelStyle, flex: '1 1 280px', minWidth: 0 }}>
          <div style={titleStyle}>Per-Particle Motion Distribution (RMS Å)</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.histogram} margin={{ top: 4, right: 8, bottom: 20, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
              <XAxis
                dataKey="bin_center"
                tick={{ fontSize: 10, fill: T.textMuted }}
                stroke={T.border}
                tickFormatter={v => Number(v).toFixed(1)}
                label={{ value: 'RMS displacement (Å)', position: 'insideBottom', offset: -10, style: { fontSize: 10, fill: T.textMuted } }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: T.textMuted }}
                stroke={T.border}
                label={{ value: 'Particles', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: T.textMuted } }}
              />
              <Tooltip
                contentStyle={{ background: T.surface, border: `1px solid ${T.border}`, fontSize: 11, borderRadius: 4 }}
                formatter={(v, name) => [v, 'Particles']}
                labelFormatter={v => `~${Number(v).toFixed(2)} Å`}
              />
              <Bar dataKey="count" fill={T.accent} opacity={0.85} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  )
}
