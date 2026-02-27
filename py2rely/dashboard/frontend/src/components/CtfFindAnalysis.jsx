import React from 'react'
import { useTheme } from '../theme.js'
import {
  ResponsiveContainer, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'

function ScatterPanel({ title, data, xKey, yKey, yLabel, yFormatter }) {
  const T = useTheme()
  return (
    <div style={{
      background: T.surface2, borderRadius: 8, padding: 12,
      border: `1px solid ${T.border}`, flex: '1 1 200px', minWidth: 0,
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 6 }}>{title}</div>
      <ResponsiveContainer width="100%" height={140}>
        <ScatterChart margin={{ top: 4, right: 8, bottom: 16, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
          <XAxis
            dataKey={xKey}
            type="number"
            name="Index"
            tick={{ fontSize: 9, fill: T.textMuted }}
            stroke={T.border}
            label={{ value: '#', position: 'insideBottom', offset: -8, style: { fontSize: 9, fill: T.textMuted } }}
          />
          <YAxis
            dataKey={yKey}
            type="number"
            name={yLabel}
            tick={{ fontSize: 9, fill: T.textMuted }}
            stroke={T.border}
            tickFormatter={yFormatter}
          />
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            contentStyle={{ background: T.surface, border: `1px solid ${T.border}`, fontSize: 10, borderRadius: 4 }}
            formatter={(v, name) => [yFormatter ? yFormatter(v) : v, name]}
          />
          <Scatter data={data} fill={T.accent} opacity={0.6} r={2} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function CtfFindAnalysis({ data }) {
  const T = useTheme()

  if (!data.micrographs?.length) {
    return (
      <div style={{ padding: 16, color: T.textMuted, fontSize: 12 }}>
        No CTF data found (micrographs_ctf.star not present — expected for STA projects).
      </div>
    )
  }

  const mics = data.micrographs

  return (
    <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <ScatterPanel
          title="Defocus U & V (μm)"
          data={[
            ...mics.map(m => ({ idx: m.idx, val: m.defocusU, series: 'U' })),
            ...mics.map(m => ({ idx: m.idx, val: m.defocusV, series: 'V' })),
          ].map(m => ({ x: m.idx, y: m.val }))}
          xKey="x" yKey="y" yLabel="Defocus (μm)"
          yFormatter={v => `${Number(v).toFixed(2)}μm`}
        />
        <ScatterPanel
          title="Astigmatism (μm)"
          data={mics.map(m => ({ x: m.idx, y: m.astigmatism }))}
          xKey="x" yKey="y" yLabel="Astigmatism (μm)"
          yFormatter={v => `${Number(v).toFixed(3)}μm`}
        />
        <ScatterPanel
          title="Max Resolution (Å)"
          data={mics.map(m => ({ x: m.idx, y: m.maxRes }))}
          xKey="x" yKey="y" yLabel="Max Res (Å)"
          yFormatter={v => `${Number(v).toFixed(1)}Å`}
        />
        <ScatterPanel
          title="CTF FOM"
          data={mics.map(m => ({ x: m.idx, y: m.fom }))}
          xKey="x" yKey="y" yLabel="FOM"
          yFormatter={v => Number(v).toFixed(3)}
        />
      </div>
    </div>
  )
}
