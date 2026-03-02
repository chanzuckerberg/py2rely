import React, { useEffect, useRef, useState } from 'react'
import { useTheme } from '../theme.js'
import { fetchLog } from '../api/http.js'

export default function LogViewer({ jobId, jobStatus, wsMessage }) {
  const theme = useTheme()
  const [log, setLog]           = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const [loading, setLoading]   = useState(false)
  const bottomRef = useRef(null)
  const prevJobId = useRef(null)

  // Fetch full log whenever the selected job changes
  useEffect(() => {
    if (!jobId) { setLog(''); return }
    prevJobId.current = jobId
    setLoading(true)
    fetchLog(jobId)
      .then(text => { if (prevJobId.current === jobId) setLog(text) })
      .catch(() => setLog('(no log available)'))
      .finally(() => setLoading(false))
  }, [jobId])

  // Poll while job is running (every 4 s)
  useEffect(() => {
    if (!jobId || jobStatus !== 'running') return
    const id = setInterval(() => {
      fetchLog(jobId).then(text => {
        if (prevJobId.current === jobId) setLog(text)
      }).catch(() => {})
    }, 4000)
    return () => clearInterval(id)
  }, [jobId, jobStatus])

  // Append individual log_line WS events for the selected job
  useEffect(() => {
    if (wsMessage?.type === 'log_line' && wsMessage.job_id === jobId) {
      setLog(prev => prev + wsMessage.line + '\n')
    }
  }, [wsMessage, jobId])

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: 'auto' })
  }, [log, autoScroll])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: theme.bg }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderBottom: `1px solid ${theme.border}`, flexShrink: 0 }}>
        <span style={{ fontSize: 11, color: theme.textMuted, fontFamily: 'monospace' }}>run.out</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button
            onClick={() => fetchLog(jobId).then(setLog).catch(() => {})}
            style={{ fontSize: 11, padding: '2px 8px', background: theme.surface2, border: `1px solid ${theme.border}`, borderRadius: 4, color: theme.text, cursor: 'pointer' }}
          >
            ↻ refresh
          </button>
          <button
            onClick={() => setAutoScroll(a => !a)}
            style={{ fontSize: 11, padding: '2px 8px', background: autoScroll ? theme.accent + '33' : theme.surface2, border: `1px solid ${autoScroll ? theme.accent : theme.border}`, borderRadius: 4, color: autoScroll ? theme.accent : theme.textMuted, cursor: 'pointer' }}
          >
            auto-scroll {autoScroll ? 'on' : 'off'}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '10px 14px' }}>
        {loading
          ? <span style={{ color: theme.textMuted, fontSize: 12 }}>Loading…</span>
          : (
            <pre style={{ margin: 0, fontSize: 11, lineHeight: 1.6, fontFamily: 'monospace', color: theme.text, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {log || '(empty)'}
            </pre>
          )
        }
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
