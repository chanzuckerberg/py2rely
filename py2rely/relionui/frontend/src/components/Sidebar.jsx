import React, { useState } from 'react'
import { useTheme, TYPE_COLOR, STATUS_COLOR } from '../theme.js'

export default function Sidebar({ pipeline, selectedId, onSelect, width = 240 }) {
  const theme = useTheme()
  const [filter, setFilter] = useState('')

  const nodes = (pipeline?.nodes ?? []).filter(n =>
    n.id.toLowerCase().includes(filter.toLowerCase()) ||
    n.type.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div style={{
      width,
      display: 'flex',
      flexDirection: 'column',
      background: theme.surface,
      borderRight: `1px solid ${theme.border}`,
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      <div style={{ padding: '8px 10px', borderBottom: `1px solid ${theme.border}` }}>
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter jobs…"
          style={{
            width: '100%',
            background: theme.surface2,
            border: `1px solid ${theme.border2}`,
            borderRadius: 6,
            padding: '5px 10px',
            color: theme.text,
            fontSize: 12,
            outline: 'none',
          }}
        />
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {(() => {
          let lastBin = null
          const items = []
          for (const node of nodes) {
            if ((node.type === 'Extract' || node.type === 'Reconstruct') && node.binfactor) {
              if (node.binfactor !== lastBin) {
                lastBin = node.binfactor
                items.push({ kind: 'header', bin: node.binfactor, key: `bin-${node.binfactor}-${node.id}` })
              }
            }
            items.push({ kind: 'node', node })
          }

          return items.map(item => {
            if (item.kind === 'header') {
              return (
                <div key={item.key} style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '8px 10px 4px',
                  marginTop: 4,
                }}>
                  <div style={{ flex: 1, height: 1, background: theme.border2 }} />
                  <span style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
                    color: theme.accent, whiteSpace: 'nowrap', flexShrink: 0,
                  }}>
                    Binning {item.bin}×
                  </span>
                  <div style={{ flex: 1, height: 1, background: theme.border2 }} />
                </div>
              )
            }

            const { node } = item
            const selected = selectedId === node.id
            return (
              <div
                key={node.id}
                onClick={() => onSelect(node.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 10px',
                  cursor: 'pointer',
                  background: selected ? theme.surface2 : 'transparent',
                  borderLeft: `3px solid ${selected ? theme.accent : 'transparent'}`,
                }}
              >
                <span style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  flexShrink: 0,
                  background: STATUS_COLOR[node.status] ?? theme.textMuted,
                }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: theme.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {node.id}
                  </div>
                  <div style={{ fontSize: 10, color: TYPE_COLOR[node.type] ?? theme.textMuted }}>
                    {node.type}
                  </div>
                </div>
              </div>
            )
          })
        })()}
      </div>
    </div>
  )
}
