import React from 'react'
import { useTheme, STATUS_COLOR } from '../theme.js'

export default function Topbar({ pipeline, wsStatus, themeName, onToggleTheme }) {
  const theme = useTheme()

  const counts = pipeline?.nodes.reduce((acc, n) => {
    acc[n.status] = (acc[n.status] || 0) + 1
    return acc
  }, {}) ?? {}

  const wsDot = { connected: '#10b981', error: '#ef4444', disconnected: '#475569' }

  return (
    <div style={{
      height: 48,
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      gap: 16,
      background: theme.surface,
      borderBottom: `1px solid ${theme.border}`,
      flexShrink: 0,
    }}>
      <span style={{ fontWeight: 700, letterSpacing: '0.05em', color: theme.accent, fontSize: 14 }}>
        py2rely-dashboard
      </span>

      {pipeline && (
        <span style={{ color: theme.textMuted, fontSize: 11, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 400 }}>
          {pipeline.project_dir}
        </span>
      )}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 14 }}>
        {Object.entries(counts).map(([status, count]) => (
          <span key={status} style={{ fontSize: 11, color: STATUS_COLOR[status] ?? theme.textMuted }}>
            {count} {status}
          </span>
        ))}

        <span
          title={`WebSocket: ${wsStatus}`}
          style={{ width: 8, height: 8, borderRadius: '50%', background: wsDot[wsStatus] ?? '#475569', display: 'inline-block' }}
        />

        <button
          onClick={onToggleTheme}
          style={{
            background: 'none',
            border: `1px solid ${theme.border}`,
            borderRadius: 6,
            color: theme.text,
            cursor: 'pointer',
            padding: '3px 8px',
            fontSize: 14,
            lineHeight: 1.4,
          }}
        >
          {themeName === 'dark' ? '☀' : '☽'}
        </button>
      </div>
    </div>
  )
}
