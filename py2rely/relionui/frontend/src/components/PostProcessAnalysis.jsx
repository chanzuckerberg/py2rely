import React from 'react'
import { useTheme } from '../theme.js'
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts'

function SummaryBox({ summary, T }) {
  if (!summary || !Object.keys(summary).length) return null

  const rows = [
    { label: 'Final resolution',   value: summary.final_resolution != null ? `${summary.final_resolution} Å` : '—' },
    { label: 'Nyquist',            value: summary.nyquist           != null ? `${summary.nyquist} Å`           : '—' },
    { label: 'B-factor',           value: summary.bfactor           != null ? `${summary.bfactor} Å²`          : '—' },
    { label: 'Phase rand. from',   value: summary.phase_rand_from   != null ? `${summary.phase_rand_from} Å`   : '—' },
    { label: 'Solvent fraction',   value: summary.solvent_fraction  != null ? `${summary.solvent_fraction}%`   : '—' },
    { label: 'Mask',               value: summary.mask              || '—' },
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
              <td style={{ padding: '5px 0', color: T.text, fontFamily: 'monospace', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function PostProcessAnalysis({ data }) {
  const T = useTheme()

  const panelStyle = {
    background: T.surface2, borderRadius: 8, padding: 12,
    border: `1px solid ${T.border}`, flex: '1 1 300px', minWidth: 0,
  }
  const titleStyle   = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 8 }
  const axisProps    = { tick: { fontSize: 10, fill: T.textMuted }, stroke: T.border }
  const gridProps    = { strokeDasharray: '3 3', stroke: T.border }
  const tooltipStyle = {
    contentStyle: { background: T.surface, border: `1px solid ${T.border}`, fontSize: 11, borderRadius: 4 },
    labelStyle: { color: T.textMuted },
  }

  if (!data.fsc?.length) {
    return (
      <div style={{ padding: 16, color: T.textMuted, fontSize: 12 }}>
        No FSC data found in postprocess.star.
      </div>
    )
  }

  return (
    <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>

        <SummaryBox summary={data.summary} T={T} />

        {/* FSC curve */}
        <div style={panelStyle}>
          <div style={titleStyle}>Post-Processing FSC</div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={data.fsc} margin={{ top: 4, right: 16, bottom: 20, left: 4 }}>
              <CartesianGrid {...gridProps} />
              <XAxis
                dataKey="resolution_a"
                reversed type="number"
                domain={['dataMax', 'dataMin']}
                {...axisProps}
                label={{ value: 'Resolution (Å)', position: 'insideBottom', offset: -10, style: { fontSize: 10, fill: T.textMuted } }}
              />
              <YAxis domain={[0, 1]} {...axisProps} />
              <ReferenceLine y={0.143} stroke="#ef4444" strokeDasharray="4 4"
                label={{ value: '0.143', fill: '#ef4444', fontSize: 9, position: 'insideTopRight' }}
              />
              <Legend wrapperStyle={{ fontSize: 10, paddingTop: 8 }} />
              <Tooltip
                {...tooltipStyle}
                formatter={v => [Number(v).toFixed(3)]}
                labelFormatter={v => `${v} Å`}
              />
              <Line type="monotone" dataKey="corrected"  name="Corrected"    stroke={T.accent}  dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="unmasked"   name="Unmasked"     stroke="#94a3b8"   dot={false} strokeWidth={1.5} strokeDasharray="6 3" />
              <Line type="monotone" dataKey="phase_rand" name="Phase-rand."  stroke="#64748b"   dot={false} strokeWidth={1.5} strokeDasharray="2 4" />
            </LineChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  )
}
